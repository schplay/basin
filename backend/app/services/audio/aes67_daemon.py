"""Client for the bondagit/aes67-linux-daemon REST API.

The daemon is responsible for SAP/mDNS stream discovery and PTP clock
synchronization. Basin queries it to resolve stream parameters (multicast
address, RTP port, channel count, sample rate) that are then passed directly
to GStreamer pipelines. No ALSA device strings are used.

In MOCK_AUDIO mode all calls return synthetic data.
"""
from __future__ import annotations

import httpx

from ...config import settings

_MOCK_STREAMS = [
    {
        "id": "mock-source-a",
        "name": "Mock Stream A",
        "address": "239.69.0.1",
        "port": 5004,
        "channels": 32,
        "sample_rate": 48000,
        "bit_depth": 24,
        "encoding_name": "L24",
    },
    {
        "id": "mock-source-b",
        "name": "Mock Stream B",
        "address": "239.69.0.2",
        "port": 5006,
        "channels": 32,
        "sample_rate": 48000,
        "bit_depth": 24,
        "encoding_name": "L24",
    },
]


async def list_daemon_streams() -> list[dict]:
    """Return all streams currently known to the AES-67 daemon."""
    if settings.mock_audio:
        return _MOCK_STREAMS

    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            resp = await client.get(f"{settings.aes67_daemon_url}/api/sources")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            return []


async def get_stream_params(multicast_address: str) -> dict | None:
    """Return stream parameters for a given multicast address from the daemon.

    Returns a dict with keys: address, port, channels, sample_rate, bit_depth,
    encoding_name — or None if the stream is not found.
    """
    if settings.mock_audio:
        for s in _MOCK_STREAMS:
            if s["address"] == multicast_address:
                return s
        return None

    streams = await list_daemon_streams()
    for s in streams:
        if s.get("address") == multicast_address:
            return s
    return None


async def get_source_status(multicast_address: str) -> dict:
    """Return live status for a configured source.

    Returns:
        stream_active  – daemon knows about this stream (SAP/mDNS discovered)
        ptp_locked     – PTP clock is synchronized (from daemon status endpoint)
        detected_channels, detected_sample_rate – from daemon if available
    """
    if settings.mock_audio:
        return {
            "stream_active": True,
            "ptp_locked": True,
            "detected_channels": 32,
            "detected_sample_rate": 48000,
        }

    params = await get_stream_params(multicast_address)
    if params is None:
        return {
            "stream_active": False,
            "ptp_locked": False,
            "detected_channels": None,
            "detected_sample_rate": None,
        }

    ptp_locked = False
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            resp = await client.get(f"{settings.aes67_daemon_url}/api/ptp/status")
            resp.raise_for_status()
            data = resp.json()
            ptp_locked = data.get("status", "") in ("locked", "tracking")
        except httpx.RequestError:
            pass

    return {
        "stream_active": True,
        "ptp_locked": ptp_locked,
        "detected_channels": params.get("channels"),
        "detected_sample_rate": params.get("sample_rate"),
    }
