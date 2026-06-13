from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class ExportStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ExportJob(Base, TimestampMixin):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codec: Mapped[str] = mapped_column(String(32), nullable=False)
    container: Mapped[str] = mapped_column(String(16), nullable=False)
    channel_selection: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    interleaved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExportStatus] = mapped_column(
        String(16), nullable=False, default=ExportStatus.queued, index=True
    )
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recording: Mapped[Recording] = relationship("Recording", back_populates="export_jobs")
    created_by_user: Mapped[User | None] = relationship("User", back_populates="export_jobs")
