from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_session
from ..deps import get_current_user, require_editor
from ..models.group import RecordingGroup
from ..models.template import RecordingTemplate
from ..models.recording import Recording, RecordingChannel, RecordingStatus
from ..models.source import AES67Source
from ..models.user import User, UserRole, user_group_access
from ..schemas.recording import (
    ChannelOut,
    RecordingCreate,
    RecordingDetailOut,
    RecordingMetadataUpdate,
    RecordingSummaryOut,
)
from ..services.audio import playback_engine, recording_engine as engine
from ..services.audit import write_audit
from ..services.groups import get_active_storage_root, sanitize_dirname

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


async def _get_recording_or_404(
    recording_id: int, session: AsyncSession, load_channels: bool = False
) -> Recording:
    if load_channels:
        result = await session.execute(
            select(Recording)
            .where(Recording.id == recording_id)
            .options(selectinload(Recording.channels))
        )
        rec = result.scalar_one_or_none()
    else:
        rec = await session.get(Recording, recording_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    return rec


async def _check_group_access(user: User, group_id: int, session: AsyncSession) -> None:
    if user.role == UserRole.admin:
        return
    result = await session.execute(
        select(user_group_access).where(
            user_group_access.c.user_id == user.id,
            user_group_access.c.group_id == group_id,
        )
    )
    if result.first() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this group")


@router.get("", response_model=list[RecordingSummaryOut])
async def list_recordings(
    group_id: int | None = None,
    status: str | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    q = select(Recording).order_by(Recording.created_at.desc())

    if group_id is not None:
        q = q.where(Recording.group_id == group_id)

    if status is not None:
        q = q.where(Recording.status == status)

    if current_user.role != UserRole.admin:
        access_result = await session.execute(
            select(user_group_access.c.group_id).where(
                user_group_access.c.user_id == current_user.id
            )
        )
        allowed_ids = [row[0] for row in access_result]
        q = q.where(Recording.group_id.in_(allowed_ids))

    if limit is not None:
        q = q.limit(limit)

    result = await session.execute(q)
    return [RecordingSummaryOut.model_validate(r) for r in result.scalars()]


@router.post("", response_model=RecordingDetailOut, status_code=status.HTTP_201_CREATED)
async def create_recording(
    body: RecordingCreate,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    # Validate group
    group = await session.get(RecordingGroup, body.group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    await _check_group_access(current_user, body.group_id, session)

    # Validate all sources
    source_ids = {c.source_id for c in body.channels}
    source_result = await session.execute(
        select(AES67Source).where(AES67Source.id.in_(source_ids))
    )
    sources_by_id = {s.id: s for s in source_result.scalars()}
    missing = source_ids - sources_by_id.keys()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sources not found: {sorted(missing)}",
        )

    # Validate each channel's source_channel is within that source's channel_count
    for ch in body.channels:
        src = sources_by_id[ch.source_id]
        if ch.source_channel > src.channel_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Channel {ch.channel_number}: source_channel {ch.source_channel} exceeds "
                    f"source '{src.name}' channel count of {src.channel_count}"
                ),
            )

    # Determine filesystem path
    rec_dir_name = sanitize_dirname(body.name)
    try:
        storage_root = await get_active_storage_root(session)
        rec_path = str(storage_root / group.filesystem_path / rec_dir_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    # Ensure uniqueness: if directory already exists the name collides
    if Path(rec_path).exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A recording directory with that name already exists in this group",
        )

    # Resolve filename pattern: body overrides template, fallback to None (default used at render time)
    filename_pattern = body.filename_pattern
    if filename_pattern is None and body.template_id:
        tmpl = await session.get(RecordingTemplate, body.template_id)
        if tmpl:
            filename_pattern = tmpl.filename_pattern

    # Create recording DB record
    recording = Recording(
        name=body.name,
        group_id=body.group_id,
        template_id=body.template_id,
        status=RecordingStatus.pending,
        filesystem_path=rec_path,
        channel_count=len(body.channels),
        sample_rate=body.sample_rate,
        bit_depth=body.bit_depth,
        codec=body.codec,
        container=body.container,
        metadata_json=body.metadata,
        filename_pattern=filename_pattern,
        created_by=current_user.id,
    )
    session.add(recording)
    await session.flush()  # Assigns recording.id

    # Create channel rows
    for ch in sorted(body.channels, key=lambda c: c.channel_number):
        channel = RecordingChannel(
            recording_id=recording.id,
            channel_number=ch.channel_number,
            source_id=ch.source_id,
            source_channel=ch.source_channel,
            channel_name=ch.channel_name,
        )
        session.add(channel)

    await session.flush()

    # Create the recording directory on disk
    Path(rec_path).mkdir(parents=True, exist_ok=True)

    # Re-query with channels loaded
    result = await session.execute(
        select(Recording)
        .where(Recording.id == recording.id)
        .options(selectinload(Recording.channels))
    )
    rec = result.scalar_one()
    return _to_detail(rec)


@router.get("/{recording_id}", response_model=RecordingDetailOut)
async def get_recording(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session, load_channels=True)
    await _check_group_access(current_user, rec.group_id, session)
    return _to_detail(rec)


@router.put("/{recording_id}", response_model=RecordingDetailOut)
async def update_recording_metadata(
    recording_id: int,
    body: RecordingMetadataUpdate,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session, load_channels=True)
    await _check_group_access(current_user, rec.group_id, session)

    if rec.status == RecordingStatus.recording:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit metadata while recording is in progress",
        )

    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        rec.name = updates["name"]
    if "metadata" in updates:
        rec.metadata_json = updates["metadata"]

    await session.flush()
    return _to_detail(rec)


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(
    recording_id: int,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session)
    await _check_group_access(current_user, rec.group_id, session)

    if rec.status == RecordingStatus.recording:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a recording that is currently in progress",
        )

    fs_path = rec.filesystem_path
    await session.delete(rec)
    await session.flush()

    p = Path(fs_path)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


@router.post("/{recording_id}/playback/start", response_model=RecordingDetailOut)
async def start_playback(
    recording_id: int,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session, load_channels=True)
    await _check_group_access(current_user, rec.group_id, session)

    if rec.status != RecordingStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Playback requires a completed recording (currently '{rec.status.value}')",
        )

    if playback_engine.is_playing(recording_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Playback is already running")

    try:
        await playback_engine.start_playback(
            recording_id=rec.id,
            filesystem_path=rec.filesystem_path,
            channel_count=rec.channel_count,
            filename_pattern=rec.filename_pattern,
            started_at=rec.started_at,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start playback: {exc}",
        )

    rec.status = RecordingStatus.playback
    await session.flush()
    return _to_detail(rec)


@router.post("/{recording_id}/playback/stop", response_model=RecordingDetailOut)
async def stop_playback(
    recording_id: int,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session, load_channels=True)
    await _check_group_access(current_user, rec.group_id, session)

    if rec.status != RecordingStatus.playback:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recording is not in playback mode (status: '{rec.status.value}')",
        )

    try:
        await playback_engine.stop_playback(recording_id)
    except RuntimeError:
        pass  # Session lost on restart; just update DB

    rec.status = RecordingStatus.completed
    await session.flush()
    return _to_detail(rec)


@router.post("/{recording_id}/start", response_model=RecordingDetailOut)
async def start_recording(
    recording_id: int,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session, load_channels=True)
    await _check_group_access(current_user, rec.group_id, session)

    if rec.status != RecordingStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recording must be in 'pending' state to start (currently '{rec.status.value}')",
        )

    if engine.is_recording(recording_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recording is already running")

    # Load source metadata
    source_ids = {ch.source_id for ch in rec.channels}
    src_result = await session.execute(
        select(AES67Source).where(AES67Source.id.in_(source_ids))
    )
    sources_map = {
        s.id: {"alsa_device": s.alsa_device, "channel_count": s.channel_count}
        for s in src_result.scalars()
    }

    channels_info = [
        {
            "channel_number": ch.channel_number,
            "source_id": ch.source_id,
            "source_channel": ch.source_channel,
        }
        for ch in rec.channels
    ]

    try:
        await engine.start_recording(
            recording_id=rec.id,
            filesystem_path=rec.filesystem_path,
            channel_count=rec.channel_count,
            sample_rate=rec.sample_rate,
            bit_depth=rec.bit_depth,
            codec=rec.codec,
            container=rec.container,
            channels=channels_info,
            sources=sources_map,
            filename_pattern=rec.filename_pattern,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start recording processes: {exc}",
        )

    rec.status = RecordingStatus.recording
    rec.started_at = datetime.now(timezone.utc)
    await write_audit(session, user_id=current_user.id, action="recording.start",
                      resource_type="recording", resource_id=rec.id,
                      detail={"name": rec.name, "channel_count": rec.channel_count})
    await session.flush()
    return _to_detail(rec)


@router.post("/{recording_id}/stop", response_model=RecordingDetailOut)
async def stop_recording(
    recording_id: int,
    current_user: User = Depends(require_editor),
    session: AsyncSession = Depends(get_session),
):
    rec = await _get_recording_or_404(recording_id, session, load_channels=True)
    await _check_group_access(current_user, rec.group_id, session)

    if rec.status != RecordingStatus.recording:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recording is not currently running (status: '{rec.status.value}')",
        )

    try:
        duration = await engine.stop_recording(recording_id)
    except RuntimeError as exc:
        # Session not found in memory (server restarted); still update DB
        duration = (
            (datetime.now(timezone.utc) - rec.started_at).total_seconds()
            if rec.started_at
            else 0.0
        )

    rec.status = RecordingStatus.completed
    rec.ended_at = datetime.now(timezone.utc)
    rec.duration_seconds = duration
    await write_audit(session, user_id=current_user.id, action="recording.stop",
                      resource_type="recording", resource_id=rec.id,
                      detail={"name": rec.name, "duration_seconds": round(duration, 2)})
    await session.flush()
    return _to_detail(rec)


def _to_detail(rec: Recording) -> RecordingDetailOut:
    channels = [
        ChannelOut(
            id=ch.id,
            channel_number=ch.channel_number,
            source_id=ch.source_id,
            source_channel=ch.source_channel,
            channel_name=ch.channel_name,
        )
        for ch in sorted(rec.channels, key=lambda c: c.channel_number)
    ]
    return RecordingDetailOut(
        id=rec.id,
        name=rec.name,
        group_id=rec.group_id,
        template_id=rec.template_id,
        status=rec.status.value if hasattr(rec.status, "value") else rec.status,
        filesystem_path=rec.filesystem_path,
        channel_count=rec.channel_count,
        sample_rate=rec.sample_rate,
        bit_depth=rec.bit_depth,
        codec=rec.codec,
        container=rec.container,
        started_at=rec.started_at,
        ended_at=rec.ended_at,
        duration_seconds=rec.duration_seconds,
        metadata_json=rec.metadata_json or {},
        filename_pattern=rec.filename_pattern,
        created_at=rec.created_at,
        channels=channels,
    )
