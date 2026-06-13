"""WebRTC monitoring endpoint — lets browsers listen to a live AES67 source.

Uses aiortc to establish a peer connection.  In MOCK_AUDIO mode the track is a
440 Hz sine wave so the feature works without physical hardware.

A global set tracks all open RTCPeerConnections so they can be cleaned up on
app shutdown (call await cleanup() from the lifespan hook).
"""
from __future__ import annotations

import logging

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_session
from ..deps import get_current_user
from ..models.source import AES67Source
from ..models.user import User
from ..schemas.monitor import MonitorAnswer, MonitorOffer

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["monitor"])

_peer_connections: set[RTCPeerConnection] = set()


async def cleanup() -> None:
    """Close all open peer connections — call from the app lifespan shutdown hook."""
    coros = [pc.close() for pc in _peer_connections]
    _peer_connections.clear()
    if coros:
        import asyncio
        await asyncio.gather(*coros, return_exceptions=True)


@router.post("/{source_id}/monitor/offer", response_model=MonitorAnswer)
async def monitor_offer(
    source_id: int,
    body: MonitorOffer,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MonitorAnswer:
    """Complete WebRTC offer/answer handshake and begin streaming source audio to the browser."""
    src = await session.get(AES67Source, source_id)
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    offer = RTCSessionDescription(sdp=body.sdp, type=body.type)
    pc = RTCPeerConnection()
    _peer_connections.add(pc)

    @pc.on("connectionstatechange")
    async def _on_state_change() -> None:
        log.debug("Monitor PC state: %s (source %d)", pc.connectionState, source_id)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            _peer_connections.discard(pc)

    if settings.mock_audio:
        # Infinite sine wave — no hardware required
        player = MediaPlayer(
            "sine=frequency=440:duration=inf:sample_rate=48000:channel_layout=stereo",
            format="lavfi",
        )
    else:
        # Read from the source's ALSA virtual card
        player = MediaPlayer(
            f"hw:{_alsa_card_index(src.alsa_device)}",
            format="alsa",
        )

    if player.audio:
        pc.addTrack(player.audio)
    else:
        _peer_connections.discard(pc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to open audio track for this source",
        )

    # Attach player so GC doesn't collect it while the connection is open
    pc._basin_player = player  # type: ignore[attr-defined]

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return MonitorAnswer(sdp=pc.localDescription.sdp, type=pc.localDescription.type)


def _alsa_card_index(alsa_device: str) -> str:
    """Extract the card index from 'hw:N' or 'hw:N,M' for use with MediaPlayer."""
    # alsa_device is e.g. "hw:0" or "hw:0,0"
    return alsa_device.split(":", 1)[-1] if ":" in alsa_device else alsa_device
