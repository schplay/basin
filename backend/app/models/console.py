from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ConsoleType(str, enum.Enum):
    behringer_x32 = "behringer_x32"
    behringer_wing = "behringer_wing"


class ConsoleIntegration(Base, TimestampMixin):
    __tablename__ = "console_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    console_type: Mapped[ConsoleType] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(48), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=10023)
    network_interface: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
