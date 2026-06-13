"""Paginated audit log endpoint (admin only)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_session
from ..deps import require_admin
from ..models.audit import AuditLog
from ..models.user import User

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditEntryOut(BaseModel):
    id: int
    user_id: int | None
    username: str | None
    action: str
    resource_type: str | None
    resource_id: int | None
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditPage(BaseModel):
    total: int
    items: list[AuditEntryOut]


@router.get("", response_model=AuditPage)
async def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    q = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
    )
    count_q = select(func.count()).select_from(AuditLog)

    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
        count_q = count_q.where(AuditLog.user_id == user_id)
    if action is not None:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
        count_q = count_q.where(AuditLog.action.ilike(f"%{action}%"))
    if resource_type is not None:
        q = q.where(AuditLog.resource_type == resource_type)
        count_q = count_q.where(AuditLog.resource_type == resource_type)

    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    q = q.offset(offset).limit(limit)
    result = await session.execute(q)
    entries = result.scalars().all()

    items = [
        AuditEntryOut(
            id=e.id,
            user_id=e.user_id,
            username=e.user.username if e.user else None,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            detail=e.detail or {},
            created_at=e.created_at,
        )
        for e in entries
    ]

    return AuditPage(total=total, items=items)
