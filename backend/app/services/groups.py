"""Filesystem synchronisation for recording groups.

The filesystem_path stored on each group is relative to the storage root, e.g.
  'Live Events/2024/Spring Tour'

Operations here keep the on-disk directory tree in sync with the DB hierarchy.
All directory mutations happen BEFORE the DB session is committed so that any
OS error rolls back the enclosing DB transaction.
"""
import re
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.group import RecordingGroup
from ..models.recording import Recording
from ..models.storage import DestinationType, StorageDestination

if TYPE_CHECKING:
    pass


def sanitize_dirname(name: str) -> str:
    """Return a filesystem-safe directory component for *name*."""
    s = name.strip()
    # Remove NUL and forward slash; replace backslash with hyphen
    s = s.replace("\x00", "").replace("/", "-").replace("\\", "-")
    # Don't start with a dot (hidden files)
    s = s.lstrip(".")
    # Collapse multiple consecutive spaces
    s = re.sub(r" {2,}", " ", s)
    return s or "group"


def build_filesystem_path(name: str, parent_path: str | None) -> str:
    part = sanitize_dirname(name)
    if parent_path:
        return f"{parent_path}/{part}"
    return part


async def get_active_storage_root(session: AsyncSession) -> Path:
    result = await session.execute(
        select(StorageDestination).where(StorageDestination.is_active == True)
    )
    dest = result.scalars().first()
    if not dest:
        raise ValueError("No active storage destination is configured")
    if dest.destination_type in (DestinationType.local_os, DestinationType.local_volume):
        if not dest.local_path:
            raise ValueError("Active destination has no local_path set")
        return Path(dest.local_path)
    raise ValueError("Network storage destinations are not yet supported for group directory sync")


def ensure_group_directory(storage_root: Path, group_path: str) -> None:
    (storage_root / group_path).mkdir(parents=True, exist_ok=True)


def rename_group_directory(storage_root: Path, old_path: str, new_path: str) -> None:
    old_dir = storage_root / old_path
    new_dir = storage_root / new_path
    if old_dir.exists() and old_dir != new_dir:
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        old_dir.rename(new_dir)


def remove_group_directory(storage_root: Path, group_path: str) -> None:
    """Remove the group directory only if it is empty."""
    d = storage_root / group_path
    if d.exists():
        d.rmdir()  # Raises OSError if non-empty — caller should handle


async def update_descendant_paths(
    old_prefix: str,
    new_prefix: str,
    session: AsyncSession,
) -> None:
    """Replace old_prefix with new_prefix for all descendant groups and recordings."""
    # Groups
    group_result = await session.execute(
        select(RecordingGroup).where(RecordingGroup.filesystem_path.like(f"{old_prefix}/%"))
    )
    for group in group_result.scalars():
        group.filesystem_path = new_prefix + group.filesystem_path[len(old_prefix):]

    # Recordings (filesystem_path is absolute so we match on the path component)
    rec_result = await session.execute(
        select(Recording).where(Recording.filesystem_path.contains(f"/{old_prefix}/"))
    )
    for rec in rec_result.scalars():
        rec.filesystem_path = rec.filesystem_path.replace(
            f"/{old_prefix}/", f"/{new_prefix}/", 1
        )


def build_tree(groups: list[RecordingGroup]) -> list[dict]:
    """Build a nested tree from a flat list of RecordingGroup ORM objects."""
    from ..schemas.group import RecordingGroupOut

    nodes: dict[int, RecordingGroupOut] = {
        g.id: RecordingGroupOut.model_validate(g) for g in groups
    }
    roots: list[RecordingGroupOut] = []
    for node in sorted(nodes.values(), key=lambda n: n.name):
        if node.parent_id is None:
            roots.append(node)
        else:
            parent = nodes.get(node.parent_id)
            if parent:
                parent.children.append(node)
    return roots
