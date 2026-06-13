"""Celery task: relocate recordings from one storage destination to another.

Uses a synchronous SQLAlchemy session (psycopg2) since Celery workers are not
async.  Progress is written to the StorageRelocation row so the API can poll it.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.recording import Recording
from ..models.storage import RelocationStatus, StorageDestination, StorageRelocation
from .celery_app import celery_app

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)


def _get_path(dest: StorageDestination) -> str:
    """Return the usable filesystem root for a destination."""
    if dest.local_path:
        return dest.local_path
    if dest.mount_point:
        return dest.mount_point
    raise ValueError(f"Destination {dest.id} has no local_path or mount_point")


@celery_app.task(bind=True, name="tasks.relocate_files")
def relocate_files(self, relocation_id: int, delete_source: bool = True) -> dict:
    with Session(_engine) as db:
        reloc = db.get(StorageRelocation, relocation_id)
        if not reloc:
            return {"error": f"Relocation {relocation_id} not found"}

        reloc.status = RelocationStatus.in_progress
        db.commit()

        try:
            src_dest = db.get(StorageDestination, reloc.from_destination_id)
            dst_dest = db.get(StorageDestination, reloc.to_destination_id)

            src_root = Path(_get_path(src_dest))
            dst_root = Path(_get_path(dst_dest))

            # Collect all files under the source root
            all_files: list[Path] = [p for p in src_root.rglob("*") if p.is_file()]
            reloc.files_total = len(all_files)
            reloc.bytes_total = sum(f.stat().st_size for f in all_files)
            db.commit()

            # Copy each file, preserving relative structure
            for idx, src_file in enumerate(all_files):
                rel = src_file.relative_to(src_root)
                dst_file = dst_root / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)

                reloc.files_moved = idx + 1
                reloc.bytes_moved += src_file.stat().st_size
                if idx % 20 == 0:
                    db.commit()  # Flush progress periodically

            # Update Recording.filesystem_path for all affected recordings
            src_prefix = str(src_root)
            recordings = db.execute(
                select(Recording).where(Recording.filesystem_path.startswith(src_prefix))
            ).scalars().all()
            for rec in recordings:
                rel_path = os.path.relpath(rec.filesystem_path, src_prefix)
                rec.filesystem_path = str(dst_root / rel_path)
            db.commit()

            # Delete source files only after all recordings' paths are updated
            if delete_source:
                for src_file in all_files:
                    src_file.unlink(missing_ok=True)
                # Remove empty directories (bottom-up)
                for dirpath, dirnames, filenames in os.walk(src_root, topdown=False):
                    try:
                        os.rmdir(dirpath)
                    except OSError:
                        pass  # Not empty — fine

            reloc.status = RelocationStatus.completed
            db.commit()
            return {"status": "completed", "files_moved": reloc.files_moved}

        except Exception as exc:
            reloc.status = RelocationStatus.failed
            db.commit()
            raise  # Re-raise so Celery marks the task as FAILURE
