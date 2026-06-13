from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ChannelConfig(BaseModel):
    channel_number: int = Field(ge=1, le=128)
    source_id: int
    source_channel: int = Field(ge=1, le=128)
    channel_name: str = Field(default="", max_length=128)


class RecordingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    group_id: int
    template_id: int | None = None
    channels: list[ChannelConfig] = Field(min_length=1)
    sample_rate: int = Field(default=48000)
    bit_depth: int = Field(default=24)
    codec: str = Field(default="pcm_s24le")
    container: str = Field(default="wav")
    metadata: dict = Field(default_factory=dict)
    filename_pattern: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_channel_numbers(self) -> "RecordingCreate":
        nums = sorted(c.channel_number for c in self.channels)
        if nums != list(range(1, len(nums) + 1)):
            raise ValueError("Channel numbers must be contiguous integers starting at 1")
        return self


class RecordingMetadataUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    metadata: dict | None = None


class ChannelOut(BaseModel):
    id: int
    channel_number: int
    source_id: int
    source_channel: int
    channel_name: str

    model_config = {"from_attributes": True}


class RecordingSummaryOut(BaseModel):
    id: int
    name: str
    group_id: int
    template_id: int | None
    status: str
    channel_count: int
    sample_rate: int
    bit_depth: int
    codec: str
    container: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecordingDetailOut(RecordingSummaryOut):
    filesystem_path: str
    metadata_json: dict
    filename_pattern: str | None
    channels: list[ChannelOut] = []
