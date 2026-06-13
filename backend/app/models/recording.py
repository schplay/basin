from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class RecordingStatus(str, enum.Enum):
    pending = "pending"
    recording = "recording"
    completed = "completed"
    error = "error"
    playback = "playback"


class Recording(Base, TimestampMixin):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recording_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recording_templates.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[RecordingStatus] = mapped_column(
        String(16), nullable=False, default=RecordingStatus.pending, index=True
    )
    filesystem_path: Mapped[str] = mapped_column(Text, nullable=False)
    channel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=48000)
    bit_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    codec: Mapped[str] = mapped_column(String(32), nullable=False, default="pcm_s24le")
    container: Mapped[str] = mapped_column(String(16), nullable=False, default="wav")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    filename_pattern: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    group: Mapped[RecordingGroup] = relationship("RecordingGroup", back_populates="recordings")
    template: Mapped[RecordingTemplate | None] = relationship("RecordingTemplate")
    created_by_user: Mapped[User | None] = relationship("User", back_populates="recordings")
    channels: Mapped[list[RecordingChannel]] = relationship(
        "RecordingChannel", back_populates="recording", cascade="all, delete-orphan",
        order_by="RecordingChannel.channel_number",
    )
    export_jobs: Mapped[list[ExportJob]] = relationship(
        "ExportJob", back_populates="recording", cascade="all, delete-orphan"
    )


class RecordingChannel(Base):
    __tablename__ = "recording_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aes67_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_channel: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    recording: Mapped[Recording] = relationship("Recording", back_populates="channels")
    source: Mapped[AES67Source] = relationship("AES67Source", back_populates="recording_channels")
