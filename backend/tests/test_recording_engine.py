"""Tests for the recording engine start/stop HTTP endpoints (MOCK_AUDIO=1)."""
import os

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import AES67Source
from app.models.storage import DestinationType, StorageDestination


@pytest.fixture(autouse=True)
def enable_mock_audio(monkeypatch):
    """Patch the already-initialised settings singleton for MOCK_AUDIO mode."""
    from app.config import settings as s
    monkeypatch.setattr(s, "mock_audio", True)


@pytest.fixture(autouse=True)
def clean_engine():
    """Reset in-memory session registry between tests; terminate any stray processes."""
    from app.services.audio import recording_engine
    recording_engine._sessions.clear()
    yield
    for s in recording_engine._sessions.values():
        for t in s._tasks:
            t.cancel()
        for proc in s.record_processes:
            if proc.returncode is None:
                proc.terminate()
        if s.meter_process and s.meter_process.returncode is None:
            s.meter_process.terminate()
    recording_engine._sessions.clear()


@pytest.fixture
async def active_storage(tmp_path, session: AsyncSession):
    dest = StorageDestination(
        name="Test Storage",
        destination_type=DestinationType.local_os,
        local_path=str(tmp_path),
        is_active=True,
    )
    session.add(dest)
    await session.commit()
    return dest


@pytest.fixture
async def source(session: AsyncSession):
    src = AES67Source(
        name="Test Source",
        multicast_address="239.0.0.1",
        network_interface="eth0",
        channel_count=8,
        sample_rate=48000,
        alsa_device="hw:0",
    )
    session.add(src)
    await session.commit()
    return src


@pytest.fixture
async def pending_recording(auth_client: AsyncClient, active_storage, source):
    group_resp = await auth_client.post("/api/groups", json={"name": "Engine Test Group"})
    group_id = group_resp.json()["id"]

    channels = [
        {"channel_number": i, "source_id": source.id, "source_channel": i, "channel_name": f"Ch {i}"}
        for i in range(1, 5)
    ]
    resp = await auth_client.post(
        "/api/recordings",
        json={
            "name": "Engine Test",
            "group_id": group_id,
            "channels": channels,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_start_recording(auth_client: AsyncClient, pending_recording):
    rid = pending_recording["id"]
    resp = await auth_client.post(f"/api/recordings/{rid}/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recording"
    assert data["started_at"] is not None


@pytest.mark.asyncio
async def test_start_recording_not_pending(auth_client: AsyncClient, pending_recording):
    rid = pending_recording["id"]
    # Start it first
    await auth_client.post(f"/api/recordings/{rid}/start")
    # Try to start again — should 409
    resp = await auth_client.post(f"/api/recordings/{rid}/start")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_stop_recording(auth_client: AsyncClient, pending_recording):
    rid = pending_recording["id"]
    await auth_client.post(f"/api/recordings/{rid}/start")

    resp = await auth_client.post(f"/api/recordings/{rid}/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["ended_at"] is not None
    assert data["duration_seconds"] is not None
    assert data["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_stop_not_recording(auth_client: AsyncClient, pending_recording):
    rid = pending_recording["id"]
    resp = await auth_client.post(f"/api/recordings/{rid}/stop")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_recording_lifecycle(auth_client: AsyncClient, pending_recording):
    rid = pending_recording["id"]

    # Initial state
    rec = (await auth_client.get(f"/api/recordings/{rid}")).json()
    assert rec["status"] == "pending"
    assert rec["started_at"] is None

    # Start
    started = (await auth_client.post(f"/api/recordings/{rid}/start")).json()
    assert started["status"] == "recording"

    # Stop
    stopped = (await auth_client.post(f"/api/recordings/{rid}/stop")).json()
    assert stopped["status"] == "completed"
    assert stopped["duration_seconds"] >= 0

    # Cannot start again (not pending)
    restart = await auth_client.post(f"/api/recordings/{rid}/start")
    assert restart.status_code == 409


@pytest.mark.asyncio
async def test_start_nonexistent_recording(auth_client: AsyncClient, active_storage):
    resp = await auth_client.post("/api/recordings/99999/start")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stop_nonexistent_recording(auth_client: AsyncClient, active_storage):
    resp = await auth_client.post("/api/recordings/99999/stop")
    assert resp.status_code == 404
