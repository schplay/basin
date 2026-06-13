from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, require_admin
from ..models.console import ConsoleIntegration
from ..models.user import User
from ..schemas.console import (
    ChannelNamesResult,
    ConsoleCreate,
    ConsoleOut,
    ConsoleUpdate,
    PingResult,
)
from ..services.osc import client as osc

router = APIRouter(prefix="/api/consoles", tags=["consoles"])


async def _get_console_or_404(console_id: int, session: AsyncSession) -> ConsoleIntegration:
    obj = await session.get(ConsoleIntegration, console_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Console not found")
    return obj


@router.get("", response_model=list[ConsoleOut])
async def list_consoles(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ConsoleIntegration).order_by(ConsoleIntegration.name))
    return [ConsoleOut.model_validate(c) for c in result.scalars()]


@router.post("", response_model=ConsoleOut, status_code=status.HTTP_201_CREATED)
async def create_console(
    body: ConsoleCreate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    obj = ConsoleIntegration(**body.model_dump())
    session.add(obj)
    await session.flush()
    return ConsoleOut.model_validate(obj)


@router.get("/{console_id}", response_model=ConsoleOut)
async def get_console(
    console_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return ConsoleOut.model_validate(await _get_console_or_404(console_id, session))


@router.put("/{console_id}", response_model=ConsoleOut)
async def update_console(
    console_id: int,
    body: ConsoleUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    obj = await _get_console_or_404(console_id, session)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    return ConsoleOut.model_validate(obj)


@router.delete("/{console_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_console(
    console_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    obj = await _get_console_or_404(console_id, session)
    await session.delete(obj)


@router.post("/{console_id}/ping", response_model=PingResult)
async def ping_console(
    console_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    obj = await _get_console_or_404(console_id, session)
    latency = await osc.ping(obj.ip_address, obj.port)
    if latency is not None:
        obj.last_connected_at = datetime.now(timezone.utc)
        await session.flush()
    return PingResult(reachable=latency is not None, latency_ms=latency)


@router.get("/{console_id}/channels", response_model=ChannelNamesResult)
async def get_console_channels(
    console_id: int,
    channel_count: int = 32,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    obj = await _get_console_or_404(console_id, session)
    if not obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Console integration is disabled",
        )
    names = await osc.get_channel_names(
        ip=obj.ip_address,
        port=obj.port,
        console_type=obj.console_type,
        channel_count=channel_count,
    )
    return ChannelNamesResult(console_id=console_id, channel_names=names)
