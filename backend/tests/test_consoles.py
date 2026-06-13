"""Tests for console integration CRUD endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_consoles_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/consoles")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_console(auth_client: AsyncClient):
    resp = await auth_client.post("/api/consoles", json={
        "name": "FOH X32",
        "console_type": "behringer_x32",
        "ip_address": "192.168.1.100",
        "port": 10023,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "FOH X32"
    assert data["console_type"] == "behringer_x32"
    assert data["port"] == 10023
    assert data["is_active"] is True
    assert data["last_connected_at"] is None


@pytest.mark.asyncio
async def test_create_wing_console(auth_client: AsyncClient):
    resp = await auth_client.post("/api/consoles", json={
        "name": "Monitor Wing",
        "console_type": "behringer_wing",
        "ip_address": "192.168.1.101",
        "port": 2223,
    })
    assert resp.status_code == 201
    assert resp.json()["console_type"] == "behringer_wing"


@pytest.mark.asyncio
async def test_list_consoles_populated(auth_client: AsyncClient):
    await auth_client.post("/api/consoles", json={
        "name": "Alpha", "console_type": "behringer_x32", "ip_address": "10.0.0.1", "port": 10023,
    })
    await auth_client.post("/api/consoles", json={
        "name": "Beta", "console_type": "behringer_wing", "ip_address": "10.0.0.2", "port": 2223,
    })
    resp = await auth_client.get("/api/consoles")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Alpha" in names
    assert "Beta" in names


@pytest.mark.asyncio
async def test_get_console(auth_client: AsyncClient):
    create = await auth_client.post("/api/consoles", json={
        "name": "My X32", "console_type": "behringer_x32", "ip_address": "10.0.1.1", "port": 10023,
    })
    cid = create.json()["id"]
    resp = await auth_client.get(f"/api/consoles/{cid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == cid


@pytest.mark.asyncio
async def test_get_console_not_found(auth_client: AsyncClient):
    resp = await auth_client.get("/api/consoles/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_console(auth_client: AsyncClient):
    create = await auth_client.post("/api/consoles", json={
        "name": "Old Name", "console_type": "behringer_x32", "ip_address": "1.1.1.1", "port": 10023,
    })
    cid = create.json()["id"]
    resp = await auth_client.put(f"/api/consoles/{cid}", json={"name": "New Name", "port": 9999})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["port"] == 9999
    assert data["ip_address"] == "1.1.1.1"  # unchanged


@pytest.mark.asyncio
async def test_delete_console(auth_client: AsyncClient):
    create = await auth_client.post("/api/consoles", json={
        "name": "To Delete", "console_type": "behringer_x32", "ip_address": "2.2.2.2", "port": 10023,
    })
    cid = create.json()["id"]
    del_resp = await auth_client.delete(f"/api/consoles/{cid}")
    assert del_resp.status_code == 204
    get_resp = await auth_client.get(f"/api/consoles/{cid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_ping_unreachable_console(auth_client: AsyncClient):
    """Ping a console at an unreachable IP — should return reachable=False, not 500."""
    create = await auth_client.post("/api/consoles", json={
        "name": "Offline", "console_type": "behringer_x32",
        "ip_address": "192.0.2.1",  # TEST-NET, guaranteed unreachable
        "port": 10023,
    })
    cid = create.json()["id"]
    resp = await auth_client.post(f"/api/consoles/{cid}/ping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reachable"] is False
    assert data["latency_ms"] is None


@pytest.mark.asyncio
async def test_channel_fetch_inactive_console_rejected(auth_client: AsyncClient):
    create = await auth_client.post("/api/consoles", json={
        "name": "Disabled", "console_type": "behringer_x32",
        "ip_address": "192.0.2.2", "port": 10023, "is_active": False,
    })
    cid = create.json()["id"]
    resp = await auth_client.get(f"/api/consoles/{cid}/channels")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_consoles_require_auth(client: AsyncClient):
    resp = await client.get("/api/consoles")
    assert resp.status_code == 401
