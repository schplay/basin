"""Tests for the audit log API."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


@pytest_asyncio.fixture
async def audit_entries(session: AsyncSession, admin_user):
    entries = [
        AuditLog(user_id=admin_user.id, action="recording.start", resource_type="recording", resource_id=1, detail={"name": "Take 1"}),
        AuditLog(user_id=admin_user.id, action="recording.stop", resource_type="recording", resource_id=1, detail={"duration_seconds": 60.0}),
        AuditLog(user_id=admin_user.id, action="export.create", resource_type="recording", resource_id=1, detail={"codec": "flac"}),
        AuditLog(user_id=None, action="user.login", resource_type="user", resource_id=None, detail={}),
    ]
    for e in entries:
        session.add(e)
    await session.commit()
    return entries


@pytest.mark.asyncio
async def test_list_audit_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_audit_returns_entries(auth_client: AsyncClient, audit_entries):
    resp = await auth_client.get("/api/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= len(audit_entries)
    assert len(data["items"]) >= len(audit_entries)


@pytest.mark.asyncio
async def test_audit_entry_has_username(auth_client: AsyncClient, audit_entries):
    resp = await auth_client.get("/api/audit")
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Find an entry with a user_id and verify username is populated
    with_user = [i for i in items if i["user_id"] is not None]
    assert len(with_user) > 0
    assert with_user[0]["username"] == "testadmin"


@pytest.mark.asyncio
async def test_audit_filter_by_action(auth_client: AsyncClient, audit_entries):
    resp = await auth_client.get("/api/audit", params={"action": "recording.start"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "recording.start" in item["action"]


@pytest.mark.asyncio
async def test_audit_filter_by_resource_type(auth_client: AsyncClient, audit_entries):
    resp = await auth_client.get("/api/audit", params={"resource_type": "recording"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    for item in data["items"]:
        assert item["resource_type"] == "recording"


@pytest.mark.asyncio
async def test_audit_filter_by_user_id(auth_client: AsyncClient, audit_entries, admin_user):
    resp = await auth_client.get("/api/audit", params={"user_id": admin_user.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    for item in data["items"]:
        assert item["user_id"] == admin_user.id


@pytest.mark.asyncio
async def test_audit_pagination(auth_client: AsyncClient, audit_entries):
    resp = await auth_client.get("/api/audit", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["total"] >= len(audit_entries)


@pytest.mark.asyncio
async def test_audit_pagination_offset(auth_client: AsyncClient, audit_entries):
    resp_page1 = await auth_client.get("/api/audit", params={"limit": 2, "offset": 0})
    resp_page2 = await auth_client.get("/api/audit", params={"limit": 2, "offset": 2})
    assert resp_page1.status_code == 200
    assert resp_page2.status_code == 200
    ids_page1 = {i["id"] for i in resp_page1.json()["items"]}
    ids_page2 = {i["id"] for i in resp_page2.json()["items"]}
    assert ids_page1.isdisjoint(ids_page2)


@pytest.mark.asyncio
async def test_audit_requires_admin(client: AsyncClient):
    resp = await client.get("/api/audit")
    assert resp.status_code == 401
