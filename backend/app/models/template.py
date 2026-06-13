from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class RecordingTemplate(Base, TimestampMixin):
    __tablename__ = "recording_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=48000)
    bit_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    codec: Mapped[str] = mapped_column(String(32), nullable=False, default="pcm_s24le")
    container: Mapped[str] = mapped_column(String(16), nullable=False, default="wav")
    channel_source_defaults: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metadata_defaults: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    filename_pattern: Mapped[str | None] = mapped_column(String(128), nullable=True)
