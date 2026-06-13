from __future__ import annotations

import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

user_group_access = Table(
    "user_group_access",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("recording_groups.id", ondelete="CASCADE"), primary_key=True),
)


class UserRole(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    operator = "operator"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.operator)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    group_access: Mapped[list[RecordingGroup]] = relationship(
        "RecordingGroup", secondary=user_group_access, back_populates="assigned_users"
    )
    recordings: Mapped[list[Recording]] = relationship("Recording", back_populates="created_by_user")
    export_jobs: Mapped[list[ExportJob]] = relationship("ExportJob", back_populates="created_by_user")
    audit_entries: Mapped[list[AuditLog]] = relationship("AuditLog", back_populates="user")
