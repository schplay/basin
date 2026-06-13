"""GStreamer level message parser for per-channel RMS/peak data.

The level element in each recording pipeline posts GstMessage objects on the
bus. _handle_bus_message in recording_engine.py calls _update_meter directly;
this module provides standalone helpers for parsing level structure values.
"""
from __future__ import annotations


def parse_level_structure(structure) -> list[tuple[float, float]]:
    """Parse a GStreamer level structure into [(rms_db, peak_db), ...] per channel.

    Returns an empty list if the structure is not a valid level message.
    """
    try:
        if structure.get_name() != "level":
            return []
        rms_array = structure.get_value("rms")
        peak_array = structure.get_value("peak")
        if rms_array is None or peak_array is None:
            return []
        return [
            (max(-90.0, float(r)), max(-90.0, float(p)))
            for r, p in zip(rms_array, peak_array)
        ]
    except Exception:
        return []
