import socket
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models.user import User, UserRole
from ..models.storage import StorageDestination, DestinationType
from ..security import get_password_hash

router = APIRouter(prefix="/api/setup", tags=["setup"])


async def _setup_complete(session: AsyncSession) -> bool:
    result = await session.execute(select(func.count()).select_from(User).where(User.role == UserRole.admin))
    return (result.scalar() or 0) > 0


class SetupStatus(BaseModel):
    complete: bool


class SetupInit(BaseModel):
    admin_password: str = Field(min_length=8)
    hostname: str = Field(min_length=1, max_length=63)
    storage_path: str = Field(min_length=1)


@router.get("/status", response_model=SetupStatus)
async def setup_status(session: AsyncSession = Depends(get_session)):
    return SetupStatus(complete=await _setup_complete(session))


@router.post("/init", status_code=status.HTTP_201_CREATED)
async def setup_init(body: SetupInit, session: AsyncSession = Depends(get_session)):
    if await _setup_complete(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup already complete")

    storage_path = Path(body.storage_path)
    try:
        storage_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot create storage path: {exc}")

    try:
        subprocess.run(["hostnamectl", "set-hostname", body.hostname], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # Non-fatal on dev machines without hostnamectl

    admin = User(
        username="admin",
        password_hash=get_password_hash(body.admin_password),
        role=UserRole.admin,
        is_active=True,
    )
    session.add(admin)
    await session.flush()

    destination = StorageDestination(
        name="Local Storage",
        destination_type=DestinationType.local_os,
        is_active=True,
        local_path=str(storage_path),
    )
    session.add(destination)

    return {"detail": "Setup complete"}
