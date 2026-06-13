import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_destinations_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/storage/destinations")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_local_destination(auth_client: AsyncClient, tmp_path):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Local SSD",
        "destination_type": "local_os",
        "local_path": str(tmp_path / "recordings"),
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Local SSD"
    assert data["is_active"] is False
    return data["id"]


@pytest.mark.asyncio
async def test_activate_destination(auth_client: AsyncClient, tmp_path):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Primary",
        "destination_type": "local_os",
        "local_path": str(tmp_path / "primary"),
    })
    dest_id = resp.json()["id"]

    activate_resp = await auth_client.post(f"/api/storage/destinations/{dest_id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_only_one_destination_active(auth_client: AsyncClient, tmp_path):
    a_resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Dest A", "destination_type": "local_os", "local_path": str(tmp_path / "a"),
    })
    b_resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Dest B", "destination_type": "local_os", "local_path": str(tmp_path / "b"),
    })
    a_id, b_id = a_resp.json()["id"], b_resp.json()["id"]

    await auth_client.post(f"/api/storage/destinations/{a_id}/activate")
    await auth_client.post(f"/api/storage/destinations/{b_id}/activate")

    a_check = await auth_client.get(f"/api/storage/destinations/{a_id}")
    b_check = await auth_client.get(f"/api/storage/destinations/{b_id}")
    assert a_check.json()["is_active"] is False
    assert b_check.json()["is_active"] is True


@pytest.mark.asyncio
async def test_capacity(auth_client: AsyncClient, tmp_path):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Cap Test",
        "destination_type": "local_os",
        "local_path": str(tmp_path / "cap"),
    })
    dest_id = resp.json()["id"]

    cap_resp = await auth_client.get(f"/api/storage/destinations/{dest_id}/capacity")
    assert cap_resp.status_code == 200
    data = cap_resp.json()
    assert data["total_gb"] > 0
    assert 0 <= data["used_pct"] <= 100


@pytest.mark.asyncio
async def test_speed_test(auth_client: AsyncClient, tmp_path):
    resp = await auth_client.post("/api/storage/destinations", json={
        "name": "Speed Test Dest",
        "destination_type": "local_os",
        "local_path": str(tmp_path / "speed"),
    })
    dest_id = resp.json()["id"]

    # Use a tiny size so the test is fast
    from app.services.storage import manager
    original_size = manager._SPEED_TEST_SIZE_MB
    manager._SPEED_TEST_SIZE_MB = 8  # 8MB for test speed

    try:
        test_resp = await auth_client.post(f"/api/storage/destinations/{dest_id}/test")
    finally:
        manager._SPEED_TEST_SIZE_MB = original_size

    assert test_resp.status_code == 200
    data = test_resp.json()
    assert data["write_mbps"] > 0
    assert data["read_mbps"] > 0
    assert len(data["safe_settings"]) > 0
