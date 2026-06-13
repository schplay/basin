from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class AES67Source(Base, TimestampMixin):
    __tablename__ = "aes67_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    network_interface: Mapped[str] = mapped_column(String(32), nullable=False)
    multicast_address: Mapped[str] = mapped_column(String(48), nullable=False)
    channel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=48000)
    bit_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    alsa_device: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    recording_channels: Mapped[list[RecordingChannel]] = relationship(
        "RecordingChannel", back_populates="source"
    )
