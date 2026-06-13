"""Tests for recording templates CRUD."""
import pytest
from httpx import AsyncClient


BASIC_TEMPLATE = {
    "name": "8-Channel Stereo",
    "channel_count": 8,
    "channel_names": ["L", "R", "C", "LFE", "LS", "RS", "LR", "RR"],
    "sample_rate": 48000,
    "bit_depth": 24,
    "codec": "pcm_s24le",
    "container": "wav",
}


@pytest.mark.asyncio
async def test_list_templates_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/templates")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_template(auth_client: AsyncClient):
    resp = await auth_client.post("/api/templates", json=BASIC_TEMPLATE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "8-Channel Stereo"
    assert data["channel_count"] == 8
    assert data["channel_names"] == ["L", "R", "C", "LFE", "LS", "RS", "LR", "RR"]
    assert data["sample_rate"] == 48000
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_channel_names_padded_to_count(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/api/templates",
        json={"name": "Padded", "channel_count": 4, "channel_names": ["L", "R"]},
    )
    assert resp.status_code == 201
    names = resp.json()["channel_names"]
    assert len(names) == 4
    assert names[0] == "L"
    assert names[1] == "R"
    assert names[2] == "Ch 3"
    assert names[3] == "Ch 4"


@pytest.mark.asyncio
async def test_channel_names_truncated_to_count(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/api/templates",
        json={
            "name": "Truncated",
            "channel_count": 2,
            "channel_names": ["A", "B", "C", "D"],
        },
    )
    assert resp.status_code == 201
    assert len(resp.json()["channel_names"]) == 2


@pytest.mark.asyncio
async def test_get_template(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/templates", json=BASIC_TEMPLATE)
    tid = create_resp.json()["id"]

    resp = await auth_client.get(f"/api/templates/{tid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == tid


@pytest.mark.asyncio
async def test_update_template_name(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/templates", json=BASIC_TEMPLATE)
    tid = create_resp.json()["id"]

    resp = await auth_client.put(f"/api/templates/{tid}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    # Other fields unchanged
    assert resp.json()["channel_count"] == 8


@pytest.mark.asyncio
async def test_update_template_channel_count_pads_names(auth_client: AsyncClient):
    create_resp = await auth_client.post(
        "/api/templates", json={"name": "Grow", "channel_count": 2, "channel_names": ["A", "B"]}
    )
    tid = create_resp.json()["id"]

    resp = await auth_client.put(f"/api/templates/{tid}", json={"channel_count": 4})
    assert resp.status_code == 200
    names = resp.json()["channel_names"]
    assert len(names) == 4
    assert names[:2] == ["A", "B"]


@pytest.mark.asyncio
async def test_delete_template(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/templates", json=BASIC_TEMPLATE)
    tid = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/templates/{tid}")
    assert del_resp.status_code == 204

    get_resp = await auth_client.get(f"/api/templates/{tid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_template_with_source_defaults(auth_client: AsyncClient):
    payload = {
        "name": "With Defaults",
        "channel_count": 2,
        "channel_source_defaults": [
            {"source_id": None, "source_channel": 1},
            {"source_id": None, "source_channel": 2},
        ],
        "metadata_defaults": {"venue": "Main Stage"},
    }
    resp = await auth_client.post("/api/templates", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["metadata_defaults"]["venue"] == "Main Stage"
    assert len(data["channel_source_defaults"]) == 2


@pytest.mark.asyncio
async def test_channel_count_max_128(auth_client: AsyncClient):
    resp = await auth_client.post(
        "/api/templates", json={"name": "Too Big", "channel_count": 129}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_templates_sorted(auth_client: AsyncClient):
    await auth_client.post("/api/templates", json={"name": "Zebra", "channel_count": 1})
    await auth_client.post("/api/templates", json={"name": "Alpha", "channel_count": 1})

    resp = await auth_client.get("/api/templates")
    names = [t["name"] for t in resp.json()]
    assert names == sorted(names)
