from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .user import user_group_access


class RecordingGroup(Base, TimestampMixin):
    __tablename__ = "recording_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recording_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    filesystem_path: Mapped[str] = mapped_column(Text, nullable=False)
    default_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recording_templates.id", ondelete="SET NULL"), nullable=True
    )

    parent: Mapped[RecordingGroup | None] = relationship(
        "RecordingGroup", remote_side="RecordingGroup.id", back_populates="children"
    )
    children: Mapped[list[RecordingGroup]] = relationship(
        "RecordingGroup", back_populates="parent", cascade="all, delete-orphan"
    )
    default_template: Mapped[RecordingTemplate | None] = relationship(
        "RecordingTemplate", foreign_keys=[default_template_id]
    )
    recordings: Mapped[list[Recording]] = relationship("Recording", back_populates="group")
    assigned_users: Mapped[list[User]] = relationship(
        "User", secondary=user_group_access, back_populates="group_access"
    )
