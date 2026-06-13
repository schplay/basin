import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_setup_status_incomplete(client: AsyncClient):
    resp = await client.get("/api/setup/status")
    assert resp.status_code == 200
    assert resp.json()["complete"] is False


@pytest.mark.asyncio
async def test_setup_init(client: AsyncClient, tmp_path):
    resp = await client.post("/api/setup/init", json={
        "admin_password": "securepass1",
        "hostname": "basin-test",
        "storage_path": str(tmp_path / "recordings"),
    })
    assert resp.status_code == 201

    status_resp = await client.get("/api/setup/status")
    assert status_resp.json()["complete"] is True


@pytest.mark.asyncio
async def test_login_success(auth_client: AsyncClient):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "testadmin"
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user):
    resp = await client.post("/api/auth/login", json={"username": "testadmin", "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(auth_client: AsyncClient):
    resp = await auth_client.post("/api/auth/logout")
    assert resp.status_code == 200

    me_resp = await auth_client.get("/api/auth/me")
    assert me_resp.status_code == 401
