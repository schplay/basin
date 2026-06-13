from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, require_admin
from ..models.template import RecordingTemplate
from ..models.user import User
from ..schemas.template import (
    RecordingTemplateCreate,
    RecordingTemplateOut,
    RecordingTemplateUpdate,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


async def _get_template_or_404(template_id: int, session: AsyncSession) -> RecordingTemplate:
    tmpl = await session.get(RecordingTemplate, template_id)
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tmpl


@router.get("", response_model=list[RecordingTemplateOut])
async def list_templates(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(RecordingTemplate).order_by(RecordingTemplate.name))
    return [RecordingTemplateOut.model_validate(t) for t in result.scalars()]


@router.post("", response_model=RecordingTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: RecordingTemplateCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    tmpl = RecordingTemplate(
        name=body.name,
        channel_count=body.channel_count,
        channel_names=body.channel_names,
        sample_rate=body.sample_rate,
        bit_depth=body.bit_depth,
        codec=body.codec,
        container=body.container,
        channel_source_defaults=[d.model_dump() for d in body.channel_source_defaults],
        metadata_defaults=body.metadata_defaults,
        filename_pattern=body.filename_pattern,
    )
    session.add(tmpl)
    await session.flush()
    return RecordingTemplateOut.model_validate(tmpl)


@router.get("/{template_id}", response_model=RecordingTemplateOut)
async def get_template(
    template_id: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tmpl = await _get_template_or_404(template_id, session)
    return RecordingTemplateOut.model_validate(tmpl)


@router.put("/{template_id}", response_model=RecordingTemplateOut)
async def update_template(
    template_id: int,
    body: RecordingTemplateUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    tmpl = await _get_template_or_404(template_id, session)
    updates = body.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field == "channel_source_defaults" and value is not None:
            setattr(tmpl, field, [d.model_dump() if hasattr(d, "model_dump") else d for d in value])
        else:
            setattr(tmpl, field, value)

    # If channel_count changed, re-pad channel_names
    if "channel_count" in updates or "channel_names" in updates:
        names = list(tmpl.channel_names or [])
        count = tmpl.channel_count
        while len(names) < count:
            names.append(f"Ch {len(names) + 1}")
        tmpl.channel_names = names[:count]

    await session.flush()
    return RecordingTemplateOut.model_validate(tmpl)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    tmpl = await _get_template_or_404(template_id, session)
    await session.delete(tmpl)
