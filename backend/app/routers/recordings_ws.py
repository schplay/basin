"""WebSocket endpoint for real-time recording meter and status data."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.audio.recording_engine import get_session

router = APIRouter(tags=["recordings-ws"])


@router.websocket("/ws/recordings/{recording_id}/meters")
async def meters_websocket(recording_id: int, websocket: WebSocket) -> None:
    """Stream per-channel RMS/peak meter data at ~10 Hz while a recording is active.

    Message shapes:
      {"type": "meters", "duration": 12.3, "channels": [{"channel": 1, "rms_db": -18.5, "peak_db": -12.0}, ...]}
      {"type": "idle"}
    """
    await websocket.accept()
    try:
        while True:
            session = get_session(recording_id)
            if session and session.is_alive():
                await websocket.send_json(
                    {
                        "type": "meters",
                        "duration": round(session.duration, 2),
                        "channels": [
                            {
                                "channel": md.channel,
                                "rms_db": round(md.rms_db, 1),
                                "peak_db": round(md.peak_db, 1),
                            }
                            for md in session.meter_data
                        ],
                    }
                )
            else:
                await websocket.send_json({"type": "idle"})
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
