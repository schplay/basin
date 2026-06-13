"""Render configurable channel filename patterns.

Supported tokens:
  {channel}   — zero-padded channel number (e.g. 001)
  {date}      — recording start date YYYYMMDD
  {time}      — recording start time HHMMSS
  {datetime}  — date and time combined YYYYMMDD_HHMMSS

Any other text is treated as a literal.

Default pattern when none is configured: ``{channel}``
"""
from __future__ import annotations

from datetime import datetime

DEFAULT_PATTERN = "{channel}"


def render_filename(pattern: str | None, channel_number: int, started_at: datetime) -> str:
    """Return the filename stem (no extension) for one channel.

    Unknown tokens are left as-is rather than raising an error.
    """
    p = pattern if pattern else DEFAULT_PATTERN
    tokens = {
        "channel": f"{channel_number:03d}",
        "date": started_at.strftime("%Y%m%d"),
        "time": started_at.strftime("%H%M%S"),
        "datetime": started_at.strftime("%Y%m%d_%H%M%S"),
    }
    try:
        return p.format_map(tokens)
    except (KeyError, ValueError):
        # Unknown or malformed tokens — substitute known ones manually and leave the rest
        result = p
        for key, value in tokens.items():
            result = result.replace(f"{{{key}}}", value)
        return result
