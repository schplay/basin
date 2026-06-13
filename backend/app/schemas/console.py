from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.console import ConsoleType


class ConsoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    console_type: ConsoleType
    ip_address: str = Field(..., min_length=7, max_length=48)
    port: int = Field(default=10023, ge=1, le=65535)
    network_interface: str | None = None
    is_active: bool = True


class ConsoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    console_type: ConsoleType | None = None
    ip_address: str | None = Field(None, min_length=7, max_length=48)
    port: int | None = Field(None, ge=1, le=65535)
    network_interface: str | None = None
    is_active: bool | None = None


class ConsoleOut(BaseModel):
    id: int
    name: str
    console_type: ConsoleType
    ip_address: str
    port: int
    network_interface: str | None
    is_active: bool
    last_connected_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PingResult(BaseModel):
    reachable: bool
    latency_ms: float | None


class ChannelNamesResult(BaseModel):
    console_id: int
    channel_names: list[str]
