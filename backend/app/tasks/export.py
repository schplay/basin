"""Celery task: transcode a completed recording's WAV files to a target format.

Progress is written to ExportJob.progress_pct so the API can poll it.
Uses a synchronous SQLAlchemy session (psycopg2) like the relocation task.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ..config import settings
from ..models.export import ExportJob, ExportStatus
from ..models.recording import Recording
from ..schemas.export import CONTAINER_EXT, CONTAINER_FORMAT
from ..services.audio.filename import render_filename
from .celery_app import celery_app

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)

_SRC_EXT = (".wav", ".aif", ".aiff")


def _find_channel_file(
    rec_path: Path,
    channel_number: int,
    filename_pattern: str | None,
    started_at: datetime | None,
) -> Path | None:
    dt = started_at or datetime.now(timezone.utc)
    stem = render_filename(filename_pattern, channel_number, dt)
    for ext in _SRC_EXT:
        p = rec_path / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _build_per_channel_cmd(
    src: Path,
    dst: Path,
    codec: str,
    container: str,
) -> list[str]:
    fmt = CONTAINER_FORMAT.get(container, container)
    cmd = ["ffmpeg", "-y", "-i", str(src), "-c:a", codec]
    if codec == "libmp3lame":
        cmd += ["-q:a", "2"]
    elif codec == "aac":
        cmd += ["-b:a", "256k"]
    cmd += ["-f", fmt, "-progress", "pipe:1", str(dst)]
    return cmd


def _build_interleaved_cmd(
    inputs: list[Path],
    dst: Path,
    codec: str,
    container: str,
) -> list[str]:
    fmt = CONTAINER_FORMAT.get(container, container)
    n = len(inputs)
    cmd = ["ffmpeg", "-y"]
    for inp in inputs:
        cmd += ["-i", str(inp)]
    if n > 1:
        cmd += ["-filter_complex", f"amerge=inputs={n}", "-ac", str(n)]
    cmd += ["-c:a", codec]
    if codec == "libmp3lame":
        cmd += ["-q:a", "2"]
    elif codec == "aac":
        cmd += ["-b:a", "256k"]
    cmd += ["-f", fmt, "-progress", "pipe:1", str(dst)]
    return cmd


def _run_ffmpeg_with_progress(
    cmd: list[str],
    duration_seconds: float | None,
    db: Session,
    job: ExportJob,
    base_pct: float,
    pct_range: float,
) -> None:
    """Run an FFmpeg command and update job.progress_pct by parsing -progress output."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if line.startswith("out_time_ms=") and duration_seconds and duration_seconds > 0:
                try:
                    out_us = int(line.split("=", 1)[1])
                    elapsed_s = out_us / 1_000_000
                    pct = base_pct + min(elapsed_s / duration_seconds, 1.0) * pct_range
                    job.progress_pct = round(pct, 1)
                    db.commit()
                except (ValueError, ZeroDivisionError):
                    pass
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg exited with code {proc.returncode}")


@celery_app.task(bind=True, name="tasks.run_export")
def run_export(self, export_job_id: int) -> dict:
    with Session(_engine) as db:
        job = db.get(ExportJob, export_job_id)
        if not job:
            return {"error": f"ExportJob {export_job_id} not found"}

        job.status = ExportStatus.running
        job.progress_pct = 0.0
        db.commit()

        try:
            rec = db.get(Recording, job.recording_id)
            if not rec:
                raise RuntimeError(f"Recording {job.recording_id} not found")

            rec_path = Path(rec.filesystem_path)
            channels = job.channel_selection or list(range(1, rec.channel_count + 1))

            # Create output directory
            out_dir = rec_path / "exports" / str(job.id)
            out_dir.mkdir(parents=True, exist_ok=True)
            job.output_path = str(out_dir)
            db.commit()

            ext = CONTAINER_EXT.get(job.container, f".{job.container}")

            if job.interleaved:
                # All selected channels merged into a single file
                inputs = []
                for ch in sorted(channels):
                    src = _find_channel_file(rec_path, ch, rec.filename_pattern, rec.started_at)
                    if src:
                        inputs.append(src)
                if not inputs:
                    raise RuntimeError("No source channel files found")

                dst = out_dir / f"export_merged{ext}"
                cmd = _build_interleaved_cmd(inputs, dst, job.codec, job.container)
                _run_ffmpeg_with_progress(cmd, rec.duration_seconds, db, job, 0.0, 100.0)
            else:
                # One file per channel
                total = len(channels)
                for idx, ch_num in enumerate(sorted(channels)):
                    src = _find_channel_file(rec_path, ch_num, rec.filename_pattern, rec.started_at)
                    if not src:
                        continue
                    dst = out_dir / f"ch{ch_num:03d}_export{ext}"
                    cmd = _build_per_channel_cmd(src, dst, job.codec, job.container)
                    base_pct = idx / total * 100
                    pct_range = 1 / total * 100
                    _run_ffmpeg_with_progress(cmd, rec.duration_seconds, db, job, base_pct, pct_range)

            job.status = ExportStatus.completed
            job.progress_pct = 100.0
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "completed", "output_path": str(out_dir)}

        except Exception as exc:
            job.status = ExportStatus.failed
            job.error_message = str(exc)
            db.commit()
            raise
