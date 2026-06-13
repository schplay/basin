from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class DestinationType(str, enum.Enum):
    local_os = "local_os"
    local_volume = "local_volume"
    network_smb = "network_smb"
    network_nfs = "network_nfs"


class RelocationStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class StorageDestination(Base, TimestampMixin):
    __tablename__ = "storage_destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_type: Mapped[DestinationType] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    network_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    network_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    network_share: Mapped[str | None] = mapped_column(Text, nullable=True)
    network_interface: Mapped[str | None] = mapped_column(String(32), nullable=True)
    smb_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    smb_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    smb_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    smb_version: Mapped[str | None] = mapped_column(String(8), nullable=True, default="auto")
    nfs_version: Mapped[str | None] = mapped_column(String(4), nullable=True)
    nfs_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    mount_point: Mapped[str | None] = mapped_column(Text, nullable=True, default="/mnt/basin-storage")
    last_speed_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_speed_test_write_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_speed_test_read_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)


class StorageRelocation(Base, TimestampMixin):
    __tablename__ = "storage_relocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_destination_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("storage_destinations.id", ondelete="RESTRICT"), nullable=False
    )
    to_destination_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("storage_destinations.id", ondelete="RESTRICT"), nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RelocationStatus] = mapped_column(
        String(16), nullable=False, default=RelocationStatus.pending
    )
    files_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_moved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_moved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    from_destination: Mapped[StorageDestination] = relationship(
        "StorageDestination", foreign_keys=[from_destination_id]
    )
    to_destination: Mapped[StorageDestination] = relationship(
        "StorageDestination", foreign_keys=[to_destination_id]
    )
