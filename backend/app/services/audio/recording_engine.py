"""Manages GStreamer pipeline sessions for active recordings.

One pipeline is created per AES-67 source involved in a recording. The pipeline
handles both capture (per-channel filesinks) and metering (level bus messages).

If the server restarts, active pipelines are lost; DB status remains 'recording'
and must be reconciled at startup (Phase 5 health check).
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
from .filename import render_filename
from .gstreamer import build_record_pipeline

log = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib  # type: ignore
    Gst.init(None)
    _GST_AVAILABLE = True
except Exception:
    _GST_AVAILABLE = False


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
    pipelines: list = field(default_factory=list)   # list[Gst.Pipeline]
    meter_data: list[ChannelMeter] = field(default_factory=list)
    _tasks: list[asyncio.Task] = field(default_factory=list)
    # Maps source_id → list of 0-based source channel indices being recorded
    _source_channel_map: dict[int, list[int]] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def is_alive(self) -> bool:
        if not self.pipelines:
            return True  # mock sessions have no pipelines
        from gi.repository import Gst  # type: ignore
        return all(
            p.get_state(0)[1] == Gst.State.PLAYING
            for p in self.pipelines
        )


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
    """Start GStreamer recording pipelines and return the new session.

    channels: [{channel_number, source_id, source_channel}]
    sources:  {source_id: {multicast_address, rtp_port, network_interface, channel_count,
                           sample_rate, bit_depth, encoding_name}}
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
        task = asyncio.create_task(_mock_meter_task(session))
        session._tasks.append(task)
    else:
        if not _GST_AVAILABLE:
            raise RuntimeError("GStreamer Python bindings (gi.repository.Gst) not installed")

        # Render filenames and group channels by source
        dt = session.started_at
        by_source: dict[int, list[dict]] = {}
        for ch in channels:
            stem = render_filename(filename_pattern, ch["channel_number"], dt)
            from .gstreamer import _SINK_MAP
            _, ext = _SINK_MAP.get((bit_depth, container), ("wavenc", ".wav"))
            ch_with_filename = {**ch, "filename": f"{stem}{ext}"}
            by_source.setdefault(ch["source_id"], []).append(ch_with_filename)

        for source_id, src_channels in by_source.items():
            src = sources[source_id]
            pipeline_desc = build_record_pipeline(
                multicast_address=src["multicast_address"],
                rtp_port=src["rtp_port"],
                network_interface=src["network_interface"],
                source_channel_count=src["channel_count"],
                channels_to_record=src_channels,
                recording_path=rec_path,
                sample_rate=src.get("sample_rate", sample_rate),
                bit_depth=src.get("bit_depth", bit_depth),
                container=container,
                encoding_name=src.get("encoding_name", "L24"),
            )
            log.info("GStreamer record pipeline (source %d): %s", source_id, pipeline_desc)

            pipeline = Gst.parse_launch(pipeline_desc)
            if pipeline is None:
                raise RuntimeError(f"Failed to parse GStreamer pipeline for source {source_id}")

            # Track which source channels map to which session channels for metering
            session._source_channel_map[source_id] = [
                c["source_channel"] - 1 for c in src_channels
            ]

            # Start bus watch for level messages and errors
            bus = pipeline.get_bus()
            bus.add_signal_watch()

            def _on_message(bus, msg, src_id=source_id, pipe=pipeline):
                _handle_bus_message(session, src_id, msg, pipe)

            bus.connect("message", _on_message)

            pipeline.set_state(Gst.State.PLAYING)
            session.pipelines.append(pipeline)

    _sessions[recording_id] = session
    log.info("Recording session started: recording_id=%d mock=%s", recording_id, settings.mock_audio)
    return session


async def stop_recording(recording_id: int) -> float:
    """Send EOS to all pipelines, wait for completion, return elapsed duration."""
    session = _sessions.pop(recording_id, None)
    if not session:
        raise RuntimeError(f"No active session for recording {recording_id}")

    for task in session._tasks:
        task.cancel()
    if session._tasks:
        await asyncio.gather(*session._tasks, return_exceptions=True)

    duration = session.duration

    if session.pipelines:
        from gi.repository import Gst  # type: ignore

        for pipeline in session.pipelines:
            pipeline.send_event(Gst.Event.new_eos())

        # Wait up to 10 s for EOS to propagate, then force NULL state
        loop = asyncio.get_event_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, _wait_eos, session.pipelines),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            log.warning("EOS timeout for recording %d — forcing NULL state", recording_id)

        for pipeline in session.pipelines:
            bus = pipeline.get_bus()
            bus.remove_signal_watch()
            pipeline.set_state(Gst.State.NULL)

    log.info("Recording session stopped: recording_id=%d duration=%.1fs", recording_id, duration)
    return duration


def _wait_eos(pipelines: list) -> None:
    """Block until all pipelines report EOS (run in executor thread)."""
    from gi.repository import Gst  # type: ignore
    for pipeline in pipelines:
        bus = pipeline.get_bus()
        bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS | Gst.MessageType.ERROR,
        )


def _handle_bus_message(
    session: RecordingSession,
    source_id: int,
    msg,
    pipeline,
) -> None:
    """GStreamer bus message callback — runs in GLib main loop thread."""
    from gi.repository import Gst  # type: ignore

    if msg.type == Gst.MessageType.ELEMENT:
        structure = msg.get_structure()
        if structure and structure.get_name() == "level":
            _update_meter(session, source_id, structure)

    elif msg.type == Gst.MessageType.ERROR:
        err, debug = msg.parse_error()
        log.error("GStreamer error (recording %d, source %d): %s — %s",
                  session.recording_id, source_id, err, debug)


def _update_meter(session: RecordingSession, source_id: int, structure) -> None:
    """Parse a GStreamer level message and update session.meter_data."""
    try:
        rms_array = structure.get_value("rms")
        peak_array = structure.get_value("peak")
        if rms_array is None or peak_array is None:
            return

        src_channels = session._source_channel_map.get(source_id, [])
        for list_idx, src_ch_idx in enumerate(src_channels):
            if src_ch_idx >= len(rms_array):
                continue
            rms = rms_array[src_ch_idx] if hasattr(rms_array, "__getitem__") else -90.0
            peak = peak_array[src_ch_idx] if hasattr(peak_array, "__getitem__") else -90.0

            # Find the session meter slot for this source channel
            # src_channels contains 0-based source channel indices in channel_number order
            channel_number = list_idx + 1  # approximate; refined below
            # Better: find by matching position in sorted channel list
            for md in session.meter_data:
                if md.channel - 1 == list_idx:
                    md.rms_db = max(-90.0, float(rms))
                    md.peak_db = max(-90.0, float(peak))
                    break
    except Exception as exc:
        log.debug("Meter parse error: %s", exc)


async def _mock_meter_task(session: RecordingSession) -> None:
    """Produce synthetic per-channel RMS/peak data for MOCK_AUDIO sessions."""
    t = 0.0
    try:
        while True:
            await asyncio.sleep(0.1)
            t += 0.1
            for md in session.meter_data:
                base = -20.0 + 8.0 * math.sin(t * 0.25 + md.channel * 0.6)
                rms = base + random.gauss(0, 1.5)
                md.rms_db = max(-90.0, min(-3.0, rms))
                md.peak_db = max(-90.0, min(0.0, md.rms_db + abs(random.gauss(4.0, 2.0))))
    except asyncio.CancelledError:
        pass
