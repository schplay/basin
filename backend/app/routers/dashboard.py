"""Dashboard aggregation endpoint."""
from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models.group import RecordingGroup
from ..models.recording import Recording, RecordingStatus
from ..models.storage import StorageDestination
from ..models.user import User, UserRole, user_group_access
from ..services.storage.manager import get_capacity

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class ActiveRecordingCard(BaseModel):
    id: int
    name: str
    group_name: str
    channel_count: int
    sample_rate: int
    bit_depth: int
    started_at: datetime | None


class RecentRecordingRow(BaseModel):
    id: int
    name: str
    group_name: str
    status: str
    channel_count: int
    duration_seconds: float | None
    created_at: datetime


class StorageSummary(BaseModel):
    name: str
    used_bytes: int
    total_bytes: int
    used_percent: float


class DashboardResponse(BaseModel):
    active_recordings: list[ActiveRecordingCard]
    recent_recordings: list[RecentRecordingRow]
    storage: StorageSummary | None
    active_recording_count: int


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    # Determine which group IDs the user can see
    if current_user.role == UserRole.admin:
        allowed_group_ids: set[int] | None = None  # No restriction
    else:
        result = await session.execute(
            select(user_group_access.c.group_id).where(
                user_group_access.c.user_id == current_user.id
            )
        )
        allowed_group_ids = {row[0] for row in result}

    # Load all recording groups for name lookup
    grp_result = await session.execute(select(RecordingGroup))
    groups_by_id = {g.id: g.name for g in grp_result.scalars()}

    def _group_name(gid: int) -> str:
        return groups_by_id.get(gid, f"Group {gid}")

    # Active recordings (status = recording)
    active_q = (
        select(Recording)
        .where(Recording.status == RecordingStatus.recording)
        .order_by(Recording.started_at)
    )
    if allowed_group_ids is not None:
        active_q = active_q.where(Recording.group_id.in_(allowed_group_ids))
    active_result = await session.execute(active_q)
    active_recs = active_result.scalars().all()

    # Recent recordings (last 10, any status except recording)
    recent_q = (
        select(Recording)
        .where(Recording.status != RecordingStatus.recording)
        .order_by(Recording.created_at.desc())
        .limit(10)
    )
    if allowed_group_ids is not None:
        recent_q = recent_q.where(Recording.group_id.in_(allowed_group_ids))
    recent_result = await session.execute(recent_q)
    recent_recs = recent_result.scalars().all()

    # Storage capacity from active destination
    storage_summary: StorageSummary | None = None
    dest_result = await session.execute(
        select(StorageDestination).where(StorageDestination.is_active == True)
    )
    dest = dest_result.scalars().first()
    if dest and dest.local_path:
        try:
            cap = await asyncio.get_event_loop().run_in_executor(
                None, get_capacity, dest.local_path
            )
            storage_summary = StorageSummary(
                name=dest.name,
                used_bytes=cap["used_bytes"],
                total_bytes=cap["total_bytes"],
                used_percent=cap["used_percent"],
            )
        except Exception:
            pass

    return DashboardResponse(
        active_recordings=[
            ActiveRecordingCard(
                id=r.id,
                name=r.name,
                group_name=_group_name(r.group_id),
                channel_count=r.channel_count,
                sample_rate=r.sample_rate,
                bit_depth=r.bit_depth,
                started_at=r.started_at,
            )
            for r in active_recs
        ],
        recent_recordings=[
            RecentRecordingRow(
                id=r.id,
                name=r.name,
                group_name=_group_name(r.group_id),
                status=r.status.value if hasattr(r.status, "value") else str(r.status),
                channel_count=r.channel_count,
                duration_seconds=r.duration_seconds,
                created_at=r.created_at,
            )
            for r in recent_recs
        ],
        storage=storage_summary,
        active_recording_count=len(active_recs),
    )
