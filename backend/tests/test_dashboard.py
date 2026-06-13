"""Tests for GET /api/dashboard."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import RecordingGroup
from app.models.recording import Recording, RecordingStatus
from app.models.storage import DestinationType, StorageDestination


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
async def group(session: AsyncSession, admin_user):
    g = RecordingGroup(name="Show A", filesystem_path="show-a")
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return g


@pytest.fixture()
async def active_storage(session: AsyncSession):
    dest = StorageDestination(
        name="Local SSD",
        destination_type=DestinationType.local_os,
        local_path="/tmp",
        is_active=True,
    )
    session.add(dest)
    await session.commit()
    await session.refresh(dest)
    return dest


@pytest.fixture()
async def completed_recording(session: AsyncSession, group, admin_user):
    rec = Recording(
        name="Night 1",
        group_id=group.id,
        status=RecordingStatus.completed,
        filesystem_path="/tmp/night1",
        channel_count=16,
        sample_rate=48000,
        bit_depth=24,
        codec="pcm_s24le",
        container="wav",
        duration_seconds=3661.5,
        created_by=admin_user.id,
    )
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return rec


@pytest.fixture()
async def active_recording(session: AsyncSession, group, admin_user):
    rec = Recording(
        name="Live Now",
        group_id=group.id,
        status=RecordingStatus.recording,
        filesystem_path="/tmp/livenow",
        channel_count=8,
        sample_rate=48000,
        bit_depth=24,
        codec="pcm_s24le",
        container="wav",
        started_at=datetime.now(timezone.utc),
        created_by=admin_user.id,
    )
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return rec


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_recording_count"] == 0
    assert data["active_recordings"] == []
    assert data["recent_recordings"] == []
    assert data["storage"] is None


@pytest.mark.asyncio
async def test_dashboard_with_active_recording(auth_client: AsyncClient, active_recording):
    resp = await auth_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_recording_count"] == 1
    assert len(data["active_recordings"]) == 1
    card = data["active_recordings"][0]
    assert card["name"] == "Live Now"
    assert card["channel_count"] == 8


@pytest.mark.asyncio
async def test_dashboard_with_completed_recording(auth_client: AsyncClient, completed_recording):
    resp = await auth_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_recording_count"] == 0
    recent = data["recent_recordings"]
    assert len(recent) >= 1
    assert recent[0]["name"] == "Night 1"
    assert recent[0]["duration_seconds"] == pytest.approx(3661.5)


@pytest.mark.asyncio
async def test_dashboard_storage_shown(auth_client: AsyncClient, active_storage):
    resp = await auth_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    if data["storage"] is not None:
        s = data["storage"]
        assert s["name"] == "Local SSD"
        assert s["total_bytes"] > 0
        assert 0.0 <= s["used_percent"] <= 100.0


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    resp = await client.get("/api/dashboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_active_not_in_recent(auth_client: AsyncClient, active_recording):
    resp = await auth_client.get("/api/dashboard")
    data = resp.json()
    recent_statuses = [r["status"] for r in data["recent_recordings"]]
    assert "recording" not in recent_statuses
