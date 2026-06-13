"""Tests for recording creation, metadata update, and deletion."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import AES67Source
from app.models.storage import DestinationType, StorageDestination


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
async def source_8ch(session: AsyncSession):
    src = AES67Source(
        name="Console 8ch",
        multicast_address="239.0.0.1",
        network_interface="eth0",
        channel_count=8,
        sample_rate=48000,
        rtp_port=5004,
    )
    session.add(src)
    await session.commit()
    return src


@pytest.fixture
async def group(auth_client: AsyncClient, active_storage):
    resp = await auth_client.post("/api/groups", json={"name": "Test Group"})
    return resp.json()


def make_channels(count: int, source_id: int):
    return [
        {"channel_number": i, "source_id": source_id, "source_channel": i, "channel_name": f"Ch {i}"}
        for i in range(1, count + 1)
    ]


@pytest.mark.asyncio
async def test_create_recording(
    auth_client: AsyncClient, active_storage, source_8ch, group, tmp_path
):
    payload = {
        "name": "Night 1",
        "group_id": group["id"],
        "channels": make_channels(4, source_8ch.id),
        "sample_rate": 48000,
        "bit_depth": 24,
        "codec": "pcm_s24le",
        "container": "wav",
    }
    resp = await auth_client.post("/api/recordings", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Night 1"
    assert data["status"] == "pending"
    assert data["channel_count"] == 4
    assert len(data["channels"]) == 4
    # Directory should be created
    import os
    assert os.path.isdir(data["filesystem_path"])


@pytest.mark.asyncio
async def test_channel_numbers_must_be_contiguous(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    payload = {
        "name": "Bad Channels",
        "group_id": group["id"],
        "channels": [
            {"channel_number": 1, "source_id": source_8ch.id, "source_channel": 1, "channel_name": ""},
            {"channel_number": 3, "source_id": source_8ch.id, "source_channel": 3, "channel_name": ""},
        ],
    }
    resp = await auth_client.post("/api/recordings", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_source_channel_exceeds_count_rejected(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    payload = {
        "name": "Over Limit",
        "group_id": group["id"],
        "channels": [
            {"channel_number": 1, "source_id": source_8ch.id, "source_channel": 99, "channel_name": ""},
        ],
    }
    resp = await auth_client.post("/api/recordings", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_source_id_rejected(
    auth_client: AsyncClient, active_storage, group
):
    payload = {
        "name": "Bad Source",
        "group_id": group["id"],
        "channels": [
            {"channel_number": 1, "source_id": 99999, "source_channel": 1, "channel_name": ""},
        ],
    }
    resp = await auth_client.post("/api/recordings", json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_group_rejected(
    auth_client: AsyncClient, active_storage, source_8ch
):
    payload = {
        "name": "Bad Group",
        "group_id": 99999,
        "channels": make_channels(1, source_8ch.id),
    }
    resp = await auth_client.post("/api/recordings", json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_recording(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    create_resp = await auth_client.post(
        "/api/recordings",
        json={"name": "Show A", "group_id": group["id"], "channels": make_channels(2, source_8ch.id)},
    )
    rid = create_resp.json()["id"]

    resp = await auth_client.get(f"/api/recordings/{rid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rid


@pytest.mark.asyncio
async def test_list_recordings(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    await auth_client.post(
        "/api/recordings",
        json={"name": "Show 1", "group_id": group["id"], "channels": make_channels(2, source_8ch.id)},
    )
    await auth_client.post(
        "/api/recordings",
        json={"name": "Show 2", "group_id": group["id"], "channels": make_channels(2, source_8ch.id)},
    )

    resp = await auth_client.get("/api/recordings")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_list_recordings_filter_by_group(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    other_group_resp = await auth_client.post("/api/groups", json={"name": "Other Group"})
    other_gid = other_group_resp.json()["id"]

    await auth_client.post(
        "/api/recordings",
        json={"name": "In Target", "group_id": group["id"], "channels": make_channels(1, source_8ch.id)},
    )
    await auth_client.post(
        "/api/recordings",
        json={"name": "In Other", "group_id": other_gid, "channels": make_channels(1, source_8ch.id)},
    )

    resp = await auth_client.get(f"/api/recordings?group_id={group['id']}")
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert "In Target" in names
    assert "In Other" not in names


@pytest.mark.asyncio
async def test_update_recording_metadata(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    create_resp = await auth_client.post(
        "/api/recordings",
        json={
            "name": "Show A",
            "group_id": group["id"],
            "channels": make_channels(1, source_8ch.id),
            "metadata": {"venue": "Old Venue"},
        },
    )
    rid = create_resp.json()["id"]

    resp = await auth_client.put(
        f"/api/recordings/{rid}",
        json={"name": "Show A Renamed", "metadata": {"venue": "New Venue"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Show A Renamed"
    assert data["metadata_json"]["venue"] == "New Venue"


@pytest.mark.asyncio
async def test_delete_recording(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    create_resp = await auth_client.post(
        "/api/recordings",
        json={"name": "To Delete", "group_id": group["id"], "channels": make_channels(1, source_8ch.id)},
    )
    rid = create_resp.json()["id"]
    fs_path = create_resp.json()["filesystem_path"]

    del_resp = await auth_client.delete(f"/api/recordings/{rid}")
    assert del_resp.status_code == 204

    import os
    assert not os.path.exists(fs_path)

    get_resp = await auth_client.get(f"/api/recordings/{rid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_create_duplicate_directory(
    auth_client: AsyncClient, active_storage, source_8ch, group, tmp_path
):
    # Pre-create the directory to simulate a collision
    import os
    group_path = (tmp_path / "Test Group" / "Collision")
    group_path.mkdir(parents=True, exist_ok=True)

    resp = await auth_client.post(
        "/api/recordings",
        json={"name": "Collision", "group_id": group["id"], "channels": make_channels(1, source_8ch.id)},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_group_with_recording_fails(
    auth_client: AsyncClient, active_storage, source_8ch, group
):
    await auth_client.post(
        "/api/recordings",
        json={"name": "Blocker", "group_id": group["id"], "channels": make_channels(1, source_8ch.id)},
    )
    resp = await auth_client.delete(f"/api/groups/{group['id']}")
    assert resp.status_code == 409
