"""Audit log write helper.

Call `write_audit` inside any router that performs a significant mutation so that
administrators can reconstruct what happened and when.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    detail: dict | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail or {},
    )
    session.add(entry)
    # No explicit flush needed — caller's transaction commits it
