"""Manages GStreamer playback sessions for completed recordings.

Reads per-channel WAV files and routes audio to a configurable output — either
an ALSA sink for local monitoring or a UDP sink to re-emit as AES-67 RTP.
In MOCK_AUDIO mode the session runs a timer with no audio output.
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

_SRC_EXT = (".wav", ".flac", ".aif", ".aiff", ".w64", ".caf")


@dataclass
class PlaybackSession:
    recording_id: int
    started_at: datetime
    pipeline: object | None = None   # Gst.Pipeline
    _task: asyncio.Task | None = None

    @property
    def duration(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def is_alive(self) -> bool:
        if self.pipeline is None:
            return self._task is not None and not self._task.done()
        try:
            from gi.repository import Gst  # type: ignore
            return self.pipeline.get_state(0)[1] == Gst.State.PLAYING
        except Exception:
            return False


_sessions: dict[int, PlaybackSession] = {}


def get_session(recording_id: int) -> PlaybackSession | None:
    return _sessions.get(recording_id)


def is_playing(recording_id: int) -> bool:
    s = _sessions.get(recording_id)
    return s is not None and s.is_alive()


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


def _build_playback_pipeline_desc(
    filesystem_path: str,
    channel_count: int,
    filename_pattern: str | None = None,
    started_at: datetime | None = None,
) -> str:
    """Build a GStreamer pipeline description for multi-channel playback.

    Reads per-channel WAV files, interleaves them, and sends to ALSA output.
    """
    path = Path(filesystem_path)
    files: list[Path] = []
    for i in range(1, channel_count + 1):
        f = _find_channel_file(path, i, filename_pattern, started_at)
        if f:
            files.append(f)

    if not files:
        raise ValueError(f"No audio files found in {filesystem_path}")

    n = len(files)
    parts: list[str] = []

    # One filesrc+wavparse branch per channel
    for idx, f in enumerate(files):
        parts.append(
            f'filesrc location="{f}" ! wavparse ! audioconvert name=ac{idx}'
        )

    # Interleave all channels and send to ALSA default output
    interleave_srcs = " ".join(f"ac{i}." for i in range(n))
    parts.append(
        f'interleave name=mix {interleave_srcs}'
        f' ! audioconvert ! alsasink device=default'
    )

    return ' '.join(parts)


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
        try:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst  # type: ignore
            Gst.init(None)
        except Exception as exc:
            raise RuntimeError("GStreamer Python bindings not available") from exc

        pipeline_desc = _build_playback_pipeline_desc(
            filesystem_path, channel_count, filename_pattern, started_at
        )
        log.info("GStreamer playback pipeline: %s", pipeline_desc)

        pipeline = Gst.parse_launch(pipeline_desc)
        if pipeline is None:
            raise RuntimeError("Failed to parse GStreamer playback pipeline")

        bus = pipeline.get_bus()
        bus.add_signal_watch()

        def _on_message(bus, msg, sess=session):
            from gi.repository import Gst as _Gst  # type: ignore
            if msg.type == _Gst.MessageType.EOS:
                _sessions.pop(sess.recording_id, None)
            elif msg.type == _Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                log.error("GStreamer playback error (recording %d): %s — %s",
                          sess.recording_id, err, debug)

        bus.connect("message", _on_message)
        pipeline.set_state(Gst.State.PLAYING)
        session.pipeline = pipeline

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

    if session.pipeline:
        try:
            from gi.repository import Gst  # type: ignore
            bus = session.pipeline.get_bus()
            bus.remove_signal_watch()
            session.pipeline.set_state(Gst.State.NULL)
        except Exception as exc:
            log.warning("Error stopping playback pipeline: %s", exc)

    log.info("Playback stopped: recording_id=%d duration=%.1fs", recording_id, duration)
    return duration


async def _mock_playback_task(session: PlaybackSession) -> None:
    try:
        await asyncio.sleep(86400)
    except asyncio.CancelledError:
        pass
