"""Manages FFmpeg playback sessions for completed recordings.

Playback sends the multi-channel WAV files back to an ALSA output device so
engineers can review takes through the console or a local monitor.  In
MOCK_AUDIO mode the session runs a timer with no audio output.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ...config import settings
from .filename import render_filename

log = logging.getLogger(__name__)

_PLAYBACK_OUTPUT_DEVICE = "default"  # Override via env / future config


@dataclass
class PlaybackSession:
    recording_id: int
    started_at: datetime
    process: asyncio.subprocess.Process | None = None
    _task: asyncio.Task | None = None

    @property
    def duration(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def is_alive(self) -> bool:
        if self.process is None:
            return self._task is not None and not self._task.done()
        return self.process.returncode is None


_sessions: dict[int, PlaybackSession] = {}


def get_session(recording_id: int) -> PlaybackSession | None:
    return _sessions.get(recording_id)


def is_playing(recording_id: int) -> bool:
    s = _sessions.get(recording_id)
    return s is not None and s.is_alive()


_SRC_EXT = (".wav", ".flac", ".aif", ".aiff", ".w64", ".caf")


def _find_channel_file(
    rec_path: Path,
    channel_number: int,
    filename_pattern: str | None,
    started_at: datetime | None,
) -> Path | None:
    dt = started_at or datetime.now(timezone.utc)
    stem = render_filename(filename_pattern, channel_number, dt)
    for ext in _SRC_EXT:
        p = rec_path / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _build_playback_command(
    filesystem_path: str,
    channel_count: int,
    filename_pattern: str | None = None,
    started_at: datetime | None = None,
) -> list[str]:
    path = Path(filesystem_path)
    inputs: list[str] = []
    for i in range(1, channel_count + 1):
        f = _find_channel_file(path, i, filename_pattern, started_at)
        if f:
            inputs += ["-i", str(f)]
    if not inputs:
        raise ValueError(f"No audio files found in {filesystem_path}")

    n = len(inputs) // 2  # each "-i file" is two list entries
    cmd = ["ffmpeg"] + inputs + [
        "-filter_complex", f"amix=inputs={n}:dropout_transition=0",
        "-f", "alsa",
        _PLAYBACK_OUTPUT_DEVICE,
    ]
    return cmd


async def start_playback(
    recording_id: int,
    filesystem_path: str,
    channel_count: int,
    filename_pattern: str | None = None,
    started_at: datetime | None = None,
) -> PlaybackSession:
    if recording_id in _sessions:
        raise RuntimeError(f"Playback session {recording_id} already active")

    session = PlaybackSession(
        recording_id=recording_id,
        started_at=datetime.now(timezone.utc),
    )

    if settings.mock_audio:
        task = asyncio.create_task(_mock_playback_task(session))
        session._task = task
    else:
        cmd = _build_playback_command(filesystem_path, channel_count, filename_pattern, started_at)
        log.info("FFmpeg playback: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        session.process = proc
        # Watch for natural end-of-file
        task = asyncio.create_task(_watch_process(session))
        session._task = task

    _sessions[recording_id] = session
    log.info("Playback started: recording_id=%d mock=%s", recording_id, settings.mock_audio)
    return session


async def stop_playback(recording_id: int) -> float:
    session = _sessions.pop(recording_id, None)
    if not session:
        raise RuntimeError(f"No active playback session for recording {recording_id}")

    if session._task:
        session._task.cancel()
        try:
            await session._task
        except (asyncio.CancelledError, Exception):
            pass

    duration = session.duration

    if session.process and session.process.returncode is None:
        session.process.terminate()
        try:
            await asyncio.wait_for(session.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            session.process.kill()
            await session.process.wait()

    log.info("Playback stopped: recording_id=%d duration=%.1fs", recording_id, duration)
    return duration


async def _mock_playback_task(session: PlaybackSession) -> None:
    """Keep the session alive until cancelled or the mock 'file' duration elapses."""
    try:
        await asyncio.sleep(86400)
    except asyncio.CancelledError:
        pass


async def _watch_process(session: PlaybackSession) -> None:
    """Remove session when FFmpeg finishes naturally (end of files)."""
    try:
        if session.process:
            await session.process.wait()
        _sessions.pop(session.recording_id, None)
    except asyncio.CancelledError:
        pass
