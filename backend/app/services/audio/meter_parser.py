"""Parse FFmpeg astats ametadata output for per-channel RMS/peak data."""
from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .recording_engine import RecordingSession

_PATTERN = re.compile(
    r'lavfi\.astats\.(\d+)\.(RMS_level|Peak_level)=([-\d.]+|-?inf)'
)


class MeterReader:
    """Reads stdout from an FFmpeg ametadata process and updates session meter data."""

    def __init__(self, session: "RecordingSession", process: asyncio.subprocess.Process):
        self.session = session
        self.process = process
        self._partial: dict[int, dict[str, float]] = {}

    async def run(self) -> None:
        try:
            while self.process.returncode is None:
                try:
                    raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if not raw:
                    break
                self._handle(raw.decode(errors="ignore").strip())
        except asyncio.CancelledError:
            pass

    def _handle(self, line: str) -> None:
        m = _PATTERN.match(line)
        if not m:
            return
        ch = int(m.group(1))  # 1-indexed
        key = m.group(2)
        try:
            value = float(m.group(3))
        except ValueError:
            value = -90.0

        self._partial.setdefault(ch, {})[key] = value

        if {"RMS_level", "Peak_level"} <= self._partial[ch].keys():
            data = self._partial.pop(ch)
            for md in self.session.meter_data:
                if md.channel == ch:
                    md.rms_db = max(-90.0, data["RMS_level"])
                    md.peak_db = max(-90.0, data["Peak_level"])
                    break
