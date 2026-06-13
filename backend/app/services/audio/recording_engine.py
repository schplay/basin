"""Manages FFmpeg subprocess sessions for active recordings.

The module maintains an in-memory registry of active recording sessions.
If the server restarts, active processes are lost; the DB status will remain
'recording' and must be reconciled at startup (Phase 5 health check).
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ...config import settings
from .ffmpeg import build_meter_command, build_record_command, start_process
from .meter_parser import MeterReader

log = logging.getLogger(__name__)


@dataclass
class ChannelMeter:
    channel: int
    rms_db: float = -90.0
    peak_db: float = -90.0


@dataclass
class RecordingSession:
    recording_id: int
    started_at: datetime
    channel_count: int
    record_processes: list[asyncio.subprocess.Process] = field(default_factory=list)
    meter_process: asyncio.subprocess.Process | None = None
    meter_data: list[ChannelMeter] = field(default_factory=list)
    _tasks: list[asyncio.Task] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def is_alive(self) -> bool:
        if not self.record_processes:
            return True  # Mock sessions have no processes
        return all(p.returncode is None for p in self.record_processes)


# Global in-process session registry
_sessions: dict[int, RecordingSession] = {}


def get_session(recording_id: int) -> RecordingSession | None:
    return _sessions.get(recording_id)


def is_recording(recording_id: int) -> bool:
    s = _sessions.get(recording_id)
    return s is not None and s.is_alive()


async def start_recording(
    recording_id: int,
    filesystem_path: str,
    channel_count: int,
    sample_rate: int,
    bit_depth: int,
    codec: str,
    container: str,
    channels: list[dict],
    sources: dict[int, dict],
    filename_pattern: str | None = None,
) -> RecordingSession:
    """Start FFmpeg recording processes and return the new session.

    channels: [{channel_number, source_id, source_channel}]
    sources:  {source_id: {alsa_device, channel_count}}
    """
    if recording_id in _sessions:
        raise RuntimeError(f"Recording {recording_id} is already active")

    rec_path = Path(filesystem_path)
    session = RecordingSession(
        recording_id=recording_id,
        started_at=datetime.now(timezone.utc),
        channel_count=channel_count,
        meter_data=[ChannelMeter(channel=i + 1) for i in range(channel_count)],
    )

    if settings.mock_audio:
        # Simulate a long-running process via `sleep`
        proc = await asyncio.create_subprocess_exec(
            "sleep", "86400",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        session.record_processes.append(proc)
        task = asyncio.create_task(_mock_meter_task(session))
        session._tasks.append(task)
    else:
        # Group channels by source for per-source FFmpeg processes
        by_source: dict[int, list[dict]] = {}
        for ch in channels:
            by_source.setdefault(ch["source_id"], []).append(ch)

        for source_id, src_channels in by_source.items():
            src = sources[source_id]
            cmd = build_record_command(
                alsa_device=src["alsa_device"],
                source_channel_count=src["channel_count"],
                channels_to_record=src_channels,
                recording_path=rec_path,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                container=container,
                filename_pattern=filename_pattern,
                started_at=session.started_at,
            )
            log.info("FFmpeg record: %s", " ".join(cmd))
            proc = await start_process(cmd)
            session.record_processes.append(proc)

        # Meter process from the first source
        if sources:
            first_src = next(iter(sources.values()))
            meter_cmd = build_meter_command(
                alsa_device=first_src["alsa_device"],
                channel_count=min(channel_count, first_src["channel_count"]),
            )
            log.info("FFmpeg meter: %s", " ".join(meter_cmd))
            meter_proc = await asyncio.create_subprocess_exec(
                *meter_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            session.meter_process = meter_proc
            reader = MeterReader(session, meter_proc)
            task = asyncio.create_task(reader.run())
            session._tasks.append(task)

    _sessions[recording_id] = session
    log.info("Recording session started: recording_id=%d mock=%s", recording_id, settings.mock_audio)
    return session


async def stop_recording(recording_id: int) -> float:
    """Terminate all processes for the session and return elapsed duration in seconds."""
    session = _sessions.pop(recording_id, None)
    if not session:
        raise RuntimeError(f"No active session for recording {recording_id}")

    # Cancel background tasks
    for task in session._tasks:
        task.cancel()
    if session._tasks:
        await asyncio.gather(*session._tasks, return_exceptions=True)

    duration = session.duration  # Capture before teardown

    # Send SIGTERM to recording processes
    for proc in session.record_processes:
        if proc.returncode is None:
            proc.terminate()
    if session.meter_process and session.meter_process.returncode is None:
        session.meter_process.terminate()

    # Wait up to 10 s for clean shutdown, then SIGKILL
    all_procs = list(session.record_processes)
    if session.meter_process:
        all_procs.append(session.meter_process)

    if all_procs:
        try:
            await asyncio.wait_for(
                asyncio.gather(*(p.wait() for p in all_procs), return_exceptions=True),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            for proc in all_procs:
                if proc.returncode is None:
                    proc.kill()
            await asyncio.gather(*(p.wait() for p in all_procs), return_exceptions=True)

    log.info("Recording session stopped: recording_id=%d duration=%.1fs", recording_id, duration)
    return duration


async def _mock_meter_task(session: RecordingSession) -> None:
    """Produce synthetic per-channel RMS/peak data for MOCK_AUDIO sessions."""
    t = 0.0
    try:
        while True:
            await asyncio.sleep(0.1)
            t += 0.1
            for md in session.meter_data:
                # Slow sine wave with per-channel phase offset + gaussian noise
                base = -20.0 + 8.0 * math.sin(t * 0.25 + md.channel * 0.6)
                rms = base + random.gauss(0, 1.5)
                md.rms_db = max(-90.0, min(-3.0, rms))
                md.peak_db = max(-90.0, min(0.0, md.rms_db + abs(random.gauss(4.0, 2.0))))
    except asyncio.CancelledError:
        pass
