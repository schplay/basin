"""FFmpeg command builder and subprocess launcher for recording."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from .filename import render_filename

# Map (bit_depth, container) → (codec, ffmpeg_format)
CODEC_MAP: dict[tuple[int, str], tuple[str, str]] = {
    (16, "wav"):  ("pcm_s16le", "wav"),
    (24, "wav"):  ("pcm_s24le", "wav"),
    (32, "wav"):  ("pcm_f32le", "wav"),
    (16, "aiff"): ("pcm_s16be", "aiff"),
    (24, "aiff"): ("pcm_s24be", "aiff"),
    (24, "rf64"): ("pcm_s24le", "rf64"),
    (32, "rf64"): ("pcm_f32le", "rf64"),
}

EXT_MAP = {"wav": ".wav", "aiff": ".aif", "rf64": ".wav"}


def build_record_command(
    alsa_device: str,
    source_channel_count: int,
    channels_to_record: list[dict],
    recording_path: Path,
    sample_rate: int,
    bit_depth: int,
    container: str,
    filename_pattern: str | None = None,
    started_at: datetime | None = None,
) -> list[str]:
    """Build an FFmpeg command that reads one ALSA device and writes per-channel WAV files.

    channels_to_record: list of dicts with {channel_number, source_channel, source_id}
    """
    codec, fmt = CODEC_MAP.get((bit_depth, container), ("pcm_s24le", "wav"))
    ext = EXT_MAP.get(container, ".wav")
    n = source_channel_count

    labels = "".join(f"[c{i}]" for i in range(n))
    filter_complex = f"[0:a]channelsplit=channel_layout={n}c{labels}"

    cmd = [
        "ffmpeg", "-y",
        "-f", "alsa",
        "-channels", str(n),
        "-i", alsa_device,
        "-filter_complex", filter_complex,
    ]

    dt = started_at or datetime.now(timezone.utc)
    for ch in sorted(channels_to_record, key=lambda c: c["channel_number"]):
        src_idx = ch["source_channel"] - 1  # 0-indexed
        stem = render_filename(filename_pattern, ch["channel_number"], dt)
        filename = f"{stem}{ext}"
        cmd.extend([
            "-map", f"[c{src_idx}]",
            "-c:a", codec,
            "-ar", str(sample_rate),
            "-f", fmt,
            str(recording_path / filename),
        ])

    return cmd


def build_meter_command(alsa_device: str, channel_count: int) -> list[str]:
    """FFmpeg command that reads ALSA and writes astats metadata to stdout.

    Python reads stdout to parse per-channel RMS/peak values at ~10 Hz.
    """
    return [
        "ffmpeg",
        "-f", "alsa",
        "-channels", str(channel_count),
        "-i", alsa_device,
        "-filter_complex", "astats=metadata=1:reset=1,ametadata=print:file=-",
        "-f", "null", "-",
    ]


async def start_process(
    cmd: list[str],
    capture_stdout: bool = False,
) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE if capture_stdout else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
