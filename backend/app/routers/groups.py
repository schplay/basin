from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, require_admin
from ..models.group import RecordingGroup
from ..models.recording import Recording
from ..models.user import User, UserRole, user_group_access
from ..schemas.group import (
    GroupAccessAssignment,
    RecordingGroupCreate,
    RecordingGroupOut,
    RecordingGroupUpdate,
)
from ..services.groups import (
    build_filesystem_path,
    build_tree,
    ensure_group_directory,
    get_active_storage_root,
    remove_group_directory,
    rename_group_directory,
    update_descendant_paths,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])


async def _check_group_access(user: User, group: RecordingGroup, session: AsyncSession) -> None:
    """Raise 403 if *user* cannot access *group*. Admins are always allowed."""
    if user.role == UserRole.admin:
        return
    result = await session.execute(
        select(user_group_access).where(
            user_group_access.c.user_id == user.id,
            user_group_access.c.group_id == group.id,
        )
    )
    if result.first() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this group")


async def _get_group_or_404(group_id: int, session: AsyncSession) -> RecordingGroup:
    group = await session.get(RecordingGroup, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.get("", response_model=list[RecordingGroupOut])
async def list_groups(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(RecordingGroup).order_by(RecordingGroup.name))
    all_groups = result.scalars().all()

    if current_user.role != UserRole.admin:
        # Filter to only groups the user has access to (and their ancestors)
        access_result = await session.execute(
            select(user_group_access.c.group_id).where(
                user_group_access.c.user_id == current_user.id
            )
        )
        allowed_ids = {row[0] for row in access_result}
        # Include parents so the tree renders correctly
        id_to_group = {g.id: g for g in all_groups}
        visible: set[int] = set()
        for gid in allowed_ids:
            g = id_to_group.get(gid)
            while g:
                visible.add(g.id)
                g = id_to_group.get(g.parent_id) if g.parent_id else None
        all_groups = [g for g in all_groups if g.id in visible]

    return build_tree(list(all_groups))


@router.post("", response_model=RecordingGroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: RecordingGroupCreate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    parent_path: str | None = None
    if body.parent_id is not None:
        parent = await _get_group_or_404(body.parent_id, session)
        parent_path = parent.filesystem_path

    fs_path = build_filesystem_path(body.name, parent_path)

    # Ensure no sibling with the same filesystem path
    existing = await session.execute(
        select(RecordingGroup).where(RecordingGroup.filesystem_path == fs_path)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A group with that name already exists at this location",
        )

    group = RecordingGroup(
        name=body.name,
        parent_id=body.parent_id,
        filesystem_path=fs_path,
        default_template_id=body.default_template_id,
    )
    session.add(group)
    await session.flush()  # Get the ID

    # Create directory (do after DB so we can roll back on OS failure)
    try:
        storage_root = await get_active_storage_root(session)
        ensure_group_directory(storage_root, fs_path)
    except ValueError:
        pass  # No storage configured yet — allow group creation anyway

    return RecordingGroupOut.model_validate(group)


@router.get("/{group_id}", response_model=RecordingGroupOut)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    group = await _get_group_or_404(group_id, session)
    await _check_group_access(current_user, group, session)
    return RecordingGroupOut.model_validate(group)


@router.put("/{group_id}", response_model=RecordingGroupOut)
async def update_group(
    group_id: int,
    body: RecordingGroupUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    group = await _get_group_or_404(group_id, session)
    old_path = group.filesystem_path
    updates = body.model_dump(exclude_unset=True)

    if "default_template_id" in updates:
        group.default_template_id = updates["default_template_id"]

    name_changed = "name" in updates and updates["name"] != group.name
    parent_changed = "parent_id" in updates and updates["parent_id"] != group.parent_id

    if name_changed:
        group.name = updates["name"]

    if parent_changed:
        new_parent_id = updates["parent_id"]
        if new_parent_id is not None:
            new_parent = await _get_group_or_404(new_parent_id, session)
            parent_path = new_parent.filesystem_path
        else:
            parent_path = None
        group.parent_id = new_parent_id

    if name_changed or parent_changed:
        # Recompute path from current parent path
        if group.parent_id is not None:
            parent = await session.get(RecordingGroup, group.parent_id)
            parent_path = parent.filesystem_path if parent else None
        else:
            parent_path = None

        new_path = build_filesystem_path(group.name, parent_path)
        group.filesystem_path = new_path

        if old_path != new_path:
            await update_descendant_paths(old_path, new_path, session)
            try:
                storage_root = await get_active_storage_root(session)
                rename_group_directory(storage_root, old_path, new_path)
            except ValueError:
                pass

    return RecordingGroupOut.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    group = await _get_group_or_404(group_id, session)

    # Reject if any child groups exist
    children = await session.execute(
        select(RecordingGroup).where(RecordingGroup.parent_id == group_id)
    )
    if children.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a group that has sub-groups",
        )

    # Reject if any recordings exist in this group
    recs = await session.execute(
        select(Recording).where(Recording.group_id == group_id)
    )
    if recs.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a group that contains recordings",
        )

    fs_path = group.filesystem_path
    await session.delete(group)
    await session.flush()

    try:
        storage_root = await get_active_storage_root(session)
        remove_group_directory(storage_root, fs_path)
    except ValueError:
        pass
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Directory is not empty and could not be removed: {e}",
        )


@router.put("/{group_id}/access", status_code=status.HTTP_204_NO_CONTENT)
async def set_group_access(
    group_id: int,
    body: GroupAccessAssignment,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    group = await _get_group_or_404(group_id, session)

    # Validate all user IDs exist
    if body.user_ids:
        result = await session.execute(
            select(User).where(User.id.in_(body.user_ids))
        )
        found_ids = {u.id for u in result.scalars()}
        missing = set(body.user_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Users not found: {sorted(missing)}",
            )

    # Replace all access entries for this group
    await session.execute(
        delete(user_group_access).where(user_group_access.c.group_id == group_id)
    )
    for uid in body.user_ids:
        await session.execute(
            user_group_access.insert().values(user_id=uid, group_id=group_id)
        )
