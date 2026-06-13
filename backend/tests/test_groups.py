"""Tests for recording groups CRUD and filesystem sync."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage import DestinationType, StorageDestination


@pytest.fixture
async def active_storage(tmp_path, session: AsyncSession):
    """Create an active local storage destination backed by tmp_path."""
    dest = StorageDestination(
        name="Test Storage",
        destination_type=DestinationType.local_os,
        local_path=str(tmp_path),
        is_active=True,
    )
    session.add(dest)
    await session.commit()
    return dest


@pytest.mark.asyncio
async def test_list_groups_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/groups")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_root_group(auth_client: AsyncClient, active_storage, tmp_path):
    resp = await auth_client.post("/api/groups", json={"name": "Live Events"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Live Events"
    assert data["filesystem_path"] == "Live Events"
    assert data["parent_id"] is None
    # Directory should have been created
    assert (tmp_path / "Live Events").is_dir()


@pytest.mark.asyncio
async def test_create_child_group(auth_client: AsyncClient, active_storage, tmp_path):
    parent_resp = await auth_client.post("/api/groups", json={"name": "Live Events"})
    parent_id = parent_resp.json()["id"]

    child_resp = await auth_client.post(
        "/api/groups", json={"name": "2024", "parent_id": parent_id}
    )
    assert child_resp.status_code == 201
    child = child_resp.json()
    assert child["filesystem_path"] == "Live Events/2024"
    assert child["parent_id"] == parent_id
    assert (tmp_path / "Live Events" / "2024").is_dir()


@pytest.mark.asyncio
async def test_list_groups_returns_tree(auth_client: AsyncClient, active_storage):
    parent_resp = await auth_client.post("/api/groups", json={"name": "Live Events"})
    parent_id = parent_resp.json()["id"]
    await auth_client.post("/api/groups", json={"name": "2024", "parent_id": parent_id})

    resp = await auth_client.get("/api/groups")
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1
    assert tree[0]["name"] == "Live Events"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["name"] == "2024"


@pytest.mark.asyncio
async def test_rename_group_moves_directory(auth_client: AsyncClient, active_storage, tmp_path):
    resp = await auth_client.post("/api/groups", json={"name": "Old Name"})
    group_id = resp.json()["id"]

    put_resp = await auth_client.put(f"/api/groups/{group_id}", json={"name": "New Name"})
    assert put_resp.status_code == 200
    assert put_resp.json()["filesystem_path"] == "New Name"
    assert not (tmp_path / "Old Name").exists()
    assert (tmp_path / "New Name").is_dir()


@pytest.mark.asyncio
async def test_rename_group_updates_child_paths(auth_client: AsyncClient, active_storage, tmp_path):
    parent_resp = await auth_client.post("/api/groups", json={"name": "Parent"})
    parent_id = parent_resp.json()["id"]
    child_resp = await auth_client.post(
        "/api/groups", json={"name": "Child", "parent_id": parent_id}
    )
    child_id = child_resp.json()["id"]

    await auth_client.put(f"/api/groups/{parent_id}", json={"name": "Renamed Parent"})

    child_detail = await auth_client.get(f"/api/groups/{child_id}")
    assert child_detail.json()["filesystem_path"] == "Renamed Parent/Child"


@pytest.mark.asyncio
async def test_delete_empty_group(auth_client: AsyncClient, active_storage, tmp_path):
    resp = await auth_client.post("/api/groups", json={"name": "To Delete"})
    group_id = resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/groups/{group_id}")
    assert del_resp.status_code == 204
    assert not (tmp_path / "To Delete").exists()


@pytest.mark.asyncio
async def test_delete_group_with_children_fails(auth_client: AsyncClient, active_storage):
    parent_resp = await auth_client.post("/api/groups", json={"name": "Parent"})
    parent_id = parent_resp.json()["id"]
    await auth_client.post("/api/groups", json={"name": "Child", "parent_id": parent_id})

    resp = await auth_client.delete(f"/api/groups/{parent_id}")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_name_same_level_rejected(auth_client: AsyncClient, active_storage):
    await auth_client.post("/api/groups", json={"name": "Unique Name"})
    resp = await auth_client.post("/api/groups", json={"name": "Unique Name"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_set_group_access(auth_client: AsyncClient, active_storage, session: AsyncSession):
    from app.models.user import User, UserRole
    from app.security import get_password_hash

    # Create a non-admin user
    user = User(
        username="editor1",
        password_hash=get_password_hash("pass"),
        role=UserRole.editor,
        is_active=True,
    )
    session.add(user)
    await session.commit()

    group_resp = await auth_client.post("/api/groups", json={"name": "Restricted"})
    group_id = group_resp.json()["id"]

    resp = await auth_client.put(
        f"/api/groups/{group_id}/access", json={"user_ids": [user.id]}
    )
    assert resp.status_code == 204
