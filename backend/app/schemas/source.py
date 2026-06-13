from datetime import datetime

from pydantic import BaseModel, Field


class AES67SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    network_interface: str = Field(min_length=1, max_length=32)
    multicast_address: str = Field(min_length=7, max_length=48)
    channel_count: int = Field(ge=1, le=64)
    sample_rate: int = Field(default=48000)
    bit_depth: int = Field(default=24)
    alsa_device: str = Field(min_length=1, max_length=128)


class AES67SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    network_interface: str | None = Field(default=None, max_length=32)
    multicast_address: str | None = Field(default=None, max_length=48)
    channel_count: int | None = Field(default=None, ge=1, le=64)
    sample_rate: int | None = None
    bit_depth: int | None = None
    alsa_device: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None


class AES67SourceOut(BaseModel):
    id: int
    name: str
    network_interface: str
    multicast_address: str
    channel_count: int
    sample_rate: int
    bit_depth: int
    alsa_device: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceStatus(BaseModel):
    source_id: int
    alsa_device: str
    alsa_present: bool
    stream_locked: bool
    detected_channels: int | None
    detected_sample_rate: int | None
