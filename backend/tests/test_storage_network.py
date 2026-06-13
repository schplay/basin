"""Tests for network storage and relocation endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.storage import DestinationType, StorageDestination


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture()
async def local_dest(auth_client: AsyncClient, tmp_path):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Local A",
        "destination_type": "local_os",
        "local_path": str(tmp_path / "dest_a"),
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
async def local_dest_b(auth_client: AsyncClient, tmp_path):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Local B",
        "destination_type": "local_os",
        "local_path": str(tmp_path / "dest_b"),
    })
    assert resp.status_code == 201
    return resp.json()


# ── Network destination creation ──────────────────────────────

@pytest.mark.asyncio
async def test_create_smb_destination(auth_client: AsyncClient):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "NAS SMB",
        "destination_type": "network_smb",
        "network_host": "192.168.1.200",
        "network_share": "recordings",
        "mount_point": "/mnt/nas-smb",
        "smb_username": "basin",
        "smb_password": "secret",
        "smb_version": "3.0",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["network_host"] == "192.168.1.200"
    assert data["network_share"] == "recordings"
    assert data["smb_username"] == "basin"
    assert "smb_password" not in data  # Password never returned
    assert "smb_password_enc" not in data


@pytest.mark.asyncio
async def test_create_nfs_destination(auth_client: AsyncClient):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "NAS NFS",
        "destination_type": "network_nfs",
        "network_host": "192.168.1.200",
        "network_share": "/exports/recordings",
        "mount_point": "/mnt/nas-nfs",
        "nfs_version": "4",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["nfs_version"] == "4"
    assert data["destination_type"] == "network_nfs"


@pytest.mark.asyncio
async def test_create_network_dest_missing_host(auth_client: AsyncClient):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Bad NFS",
        "destination_type": "network_nfs",
        "network_share": "/exports/recordings",  # host missing
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_smb_password(auth_client: AsyncClient):
    create = await auth_client.post("/api/storage/destinations", json={
        "name": "SMB Update Test",
        "destination_type": "network_smb",
        "network_host": "10.0.0.5",
        "network_share": "data",
        "smb_username": "user1",
        "smb_password": "oldpass",
    })
    cid = create.json()["id"]
    update = await auth_client.put(f"/api/storage/destinations/{cid}", json={
        "smb_password": "newpass",
        "smb_username": "user2",
    })
    assert update.status_code == 200
    assert update.json()["smb_username"] == "user2"


@pytest.mark.asyncio
async def test_mount_endpoint_rejects_local_dest(auth_client: AsyncClient, local_dest):
    resp = await auth_client.post(f"/api/storage/destinations/{local_dest['id']}/mount")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_test_connection_rejects_local_dest(auth_client: AsyncClient, local_dest):
    resp = await auth_client.post(f"/api/storage/destinations/{local_dest['id']}/test-connection")
    assert resp.status_code == 400


# ── Relocation ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_relocations_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/storage/relocations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_relocation_same_dest_rejected(auth_client: AsyncClient, local_dest):
    resp = await auth_client.post("/api/storage/relocations", json={
        "from_destination_id": local_dest["id"],
        "to_destination_id": local_dest["id"],
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_relocation_missing_dest(auth_client: AsyncClient, local_dest):
    resp = await auth_client.post("/api/storage/relocations", json={
        "from_destination_id": local_dest["id"],
        "to_destination_id": 99999,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_pending_relocation(auth_client: AsyncClient, local_dest, local_dest_b, monkeypatch):
    # Patch Celery task to not actually run
    from app.tasks import relocate as rel_module
    monkeypatch.setattr(rel_module.relocate_files, "delay", lambda *a, **kw: type("T", (), {"id": "mock-task"})())

    create = await auth_client.post("/api/storage/relocations", json={
        "from_destination_id": local_dest["id"],
        "to_destination_id": local_dest_b["id"],
    })
    assert create.status_code == 201
    rid = create.json()["id"]

    cancel = await auth_client.delete(f"/api/storage/relocations/{rid}")
    assert cancel.status_code == 204

    get = await auth_client.get(f"/api/storage/relocations/{rid}")
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_relocation_requires_admin(client: AsyncClient):
    resp = await client.get("/api/storage/relocations")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_relocation_not_found(auth_client: AsyncClient):
    resp = await auth_client.get("/api/storage/relocations/99999")
    assert resp.status_code == 404
