from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, require_editor
from ..models.source import AES67Source
from ..models.user import User
from ..schemas.source import AES67SourceCreate, AES67SourceOut, AES67SourceUpdate, SourceStatus
from ..services.audio.aes67_daemon import get_source_status

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[AES67SourceOut])
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    result = await session.execute(select(AES67Source).order_by(AES67Source.name))
    return [AES67SourceOut.model_validate(s) for s in result.scalars()]


@router.post("", response_model=AES67SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: AES67SourceCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
):
    source = AES67Source(**body.model_dump())
    session.add(source)
    await session.flush()
    return AES67SourceOut.model_validate(source)


@router.get("/{source_id}", response_model=AES67SourceOut)
async def get_source(
    source_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    source = await session.get(AES67Source, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return AES67SourceOut.model_validate(source)


@router.put("/{source_id}", response_model=AES67SourceOut)
async def update_source(
    source_id: int,
    body: AES67SourceUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
):
    source = await session.get(AES67Source, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(source, field, value)

    return AES67SourceOut.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
):
    source = await session.get(AES67Source, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    await session.delete(source)


@router.get("/{source_id}/status", response_model=SourceStatus)
async def source_status(
    source_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    source = await session.get(AES67Source, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    live = await get_source_status(source.multicast_address)
    return SourceStatus(source_id=source_id, multicast_address=source.multicast_address, **live)
