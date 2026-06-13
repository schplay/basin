"""Client for the bondagit/aes67-linux-daemon REST API.

In MOCK_AUDIO mode all calls return synthetic data so the backend
can be exercised without the kernel module or a live AES-67 stream.
"""
from pathlib import Path

import httpx

from ...config import settings

_MOCK_STREAMS = [
    {
        "id": "mock-source-a",
        "name": "Mock Stream A",
        "address": "239.69.0.1",
        "channels": 32,
        "sample_rate": 48000,
        "bit_depth": 24,
    },
    {
        "id": "mock-source-b",
        "name": "Mock Stream B",
        "address": "239.69.0.2",
        "channels": 32,
        "sample_rate": 48000,
        "bit_depth": 24,
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


def _card_name_from_alsa_device(alsa_device: str) -> str:
    """Extract card name from e.g. 'hw:AES67_Studio,0' → 'AES67_Studio'."""
    try:
        return alsa_device.split(":")[1].split(",")[0]
    except IndexError:
        return alsa_device


def _alsa_card_present(card_name: str) -> bool:
    """Check /proc/asound/cards for the named card without opening the device."""
    try:
        content = Path("/proc/asound/cards").read_text()
        return card_name in content
    except OSError:
        return False


async def get_source_status(alsa_device: str) -> dict:
    """Return live status for a configured source.

    Returns:
        alsa_present   – card is registered in ALSA (stream is being received)
        stream_locked  – PTP-locked and receiving (same as alsa_present for now;
                         extended via daemon subscription in a future phase)
        detected_channels, detected_sample_rate – from daemon if available
    """
    if settings.mock_audio:
        return {
            "alsa_present": True,
            "stream_locked": True,
            "detected_channels": 32,
            "detected_sample_rate": 48000,
        }

    card_name = _card_name_from_alsa_device(alsa_device)
    alsa_present = _alsa_card_present(card_name)

    detected_channels = None
    detected_sample_rate = None

    # Try to get richer info from the daemon
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            resp = await client.get(f"{settings.aes67_daemon_url}/api/sources")
            resp.raise_for_status()
            for stream in resp.json():
                if card_name.lower() in stream.get("name", "").lower():
                    detected_channels = stream.get("channels")
                    detected_sample_rate = stream.get("sample_rate")
                    break
        except httpx.RequestError:
            pass

    return {
        "alsa_present": alsa_present,
        "stream_locked": alsa_present,
        "detected_channels": detected_channels,
        "detected_sample_rate": detected_sample_rate,
    }
