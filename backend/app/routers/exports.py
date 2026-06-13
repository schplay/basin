"""Export job API — create and track FFmpeg transcode jobs for completed recordings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_session
from ..deps import get_current_user, require_editor
from ..models.export import ExportJob, ExportStatus
from ..models.recording import Recording, RecordingStatus
from ..models.user import User, UserRole, user_group_access
from ..schemas.export import ExportJobCreate, ExportJobOut, EXPORT_PRESETS
from ..services.audit import write_audit
from ..tasks.export import run_export

router = APIRouter(tags=["exports"])


async def _check_recording_access(
    recording_id: int,
    user: User,
    session: AsyncSession,
) -> Recording:
    rec = await session.get(Recording, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    if user.role != UserRole.admin:
        result = await session.execute(
            select(user_group_access).where(
                user_group_access.c.user_id == user.id,
                user_group_access.c.group_id == rec.group_id,
            )
        )
        if result.first() is None:
            raise HTTPException(status_code=403, detail="Access denied to this recording")

    return rec


@router.get("/api/export-presets")
async def get_export_presets(_=Depends(get_current_user)):
    return EXPORT_PRESETS


@router.get("/api/recordings/{recording_id}/exports", response_model=list[ExportJobOut])
async def list_exports(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _check_recording_access(recording_id, current_user, session)
    result = await session.execute(
        select(ExportJob)
        .where(ExportJob.recording_id == recording_id)
        .order_by(ExportJob.created_at.desc())
    )
    return [ExportJobOut.model_validate(j) for j in result.scalars()]


@router.post(
    "/api/recordings/{recording_id}/exports",
    response_model=ExportJobOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_export(
    recording_id: int,
    body: ExportJobCreate,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _check_recording_access(recording_id, current_user, session)

    if rec.status not in (RecordingStatus.completed, RecordingStatus.playback):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Can only export completed recordings (current status: '{rec.status.value}')",
        )

    # Validate channel selection against actual channel count
    if body.channel_selection:
        invalid = [c for c in body.channel_selection if c < 1 or c > rec.channel_count]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Channel numbers out of range (1–{rec.channel_count}): {invalid}",
            )

    job = ExportJob(
        recording_id=recording_id,
        codec=body.codec,
        container=body.container,
        channel_selection=body.channel_selection,
        interleaved=body.interleaved,
        status=ExportStatus.queued,
        created_by=current_user.id,
    )
    session.add(job)
    await session.flush()

    await write_audit(
        session,
        user_id=current_user.id,
        action="export.create",
        resource_type="recording",
        resource_id=recording_id,
        detail={"codec": body.codec, "container": body.container, "interleaved": body.interleaved},
    )

    task = run_export.delay(job.id)
    job.celery_task_id = task.id
    await session.flush()

    return ExportJobOut.model_validate(job)


@router.get("/api/exports/{job_id}", response_model=ExportJobOut)
async def get_export(
    job_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(ExportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    await _check_recording_access(job.recording_id, current_user, session)
    return ExportJobOut.model_validate(job)


@router.delete("/api/exports/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export(
    job_id: int,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(ExportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    await _check_recording_access(job.recording_id, current_user, session)

    if job.status == ExportStatus.running:
        raise HTTPException(status_code=409, detail="Cannot delete a running export job")

    await session.delete(job)
