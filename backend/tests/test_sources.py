import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_sources_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/sources")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_source(auth_client: AsyncClient):
    resp = await auth_client.post("/api/sources", json={
        "name": "Studio FOH",
        "network_interface": "eth0",
        "multicast_address": "239.69.0.1",
        "channel_count": 32,
        "sample_rate": 48000,
        "bit_depth": 24,
        "rtp_port": 5004,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Studio FOH"
    assert data["channel_count"] == 32
    assert data["is_active"] is True
    return data["id"]


@pytest.mark.asyncio
async def test_create_source_exceeds_channel_limit(auth_client: AsyncClient):
    resp = await auth_client.post("/api/sources", json={
        "name": "Too Many Channels",
        "network_interface": "eth0",
        "multicast_address": "239.69.0.99",
        "channel_count": 256,
        "sample_rate": 48000,
        "bit_depth": 24,
        "rtp_port": 5006,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_source(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/sources", json={
        "name": "To Rename",
        "network_interface": "eth0",
        "multicast_address": "239.69.1.1",
        "channel_count": 16,
        "sample_rate": 48000,
        "bit_depth": 24,
        "rtp_port": 5008,
    })
    source_id = create_resp.json()["id"]

    resp = await auth_client.put(f"/api/sources/{source_id}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


@pytest.mark.asyncio
async def test_source_status_mock(auth_client: AsyncClient, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.settings, "mock_audio", True)

    create_resp = await auth_client.post("/api/sources", json={
        "name": "Mock Source",
        "network_interface": "eth0",
        "multicast_address": "239.69.2.1",
        "channel_count": 32,
        "sample_rate": 48000,
        "bit_depth": 24,
        "rtp_port": 5010,
    })
    source_id = create_resp.json()["id"]

    resp = await auth_client.get(f"/api/sources/{source_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stream_active"] is True
    assert data["ptp_locked"] is True


@pytest.mark.asyncio
async def test_delete_source(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/sources", json={
        "name": "To Delete",
        "network_interface": "eth0",
        "multicast_address": "239.69.3.1",
        "channel_count": 8,
        "sample_rate": 48000,
        "bit_depth": 24,
        "rtp_port": 5012,
    })
    source_id = create_resp.json()["id"]

    resp = await auth_client.delete(f"/api/sources/{source_id}")
    assert resp.status_code == 204

    resp = await auth_client.get(f"/api/sources/{source_id}")
    assert resp.status_code == 404
