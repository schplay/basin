from datetime import datetime

from pydantic import BaseModel, Field


class AES67SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    network_interface: str = Field(min_length=1, max_length=32)
    multicast_address: str = Field(min_length=7, max_length=48)
    rtp_port: int = Field(default=5004, ge=1024, le=65535)
    channel_count: int = Field(ge=1, le=128)
    sample_rate: int = Field(default=48000)
    bit_depth: int = Field(default=24)
    encoding_name: str = Field(default="L24", max_length=8)


class AES67SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    network_interface: str | None = Field(default=None, max_length=32)
    multicast_address: str | None = Field(default=None, max_length=48)
    rtp_port: int | None = Field(default=None, ge=1024, le=65535)
    channel_count: int | None = Field(default=None, ge=1, le=128)
    sample_rate: int | None = None
    bit_depth: int | None = None
    encoding_name: str | None = Field(default=None, max_length=8)
    is_active: bool | None = None


class AES67SourceOut(BaseModel):
    id: int
    name: str
    network_interface: str
    multicast_address: str
    rtp_port: int
    channel_count: int
    sample_rate: int
    bit_depth: int
    encoding_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceStatus(BaseModel):
    source_id: int
    multicast_address: str
    stream_active: bool
    ptp_locked: bool
    detected_channels: int | None
    detected_sample_rate: int | None
