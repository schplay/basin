from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ChannelSourceDefault(BaseModel):
    source_id: int | None = None
    source_channel: int = 1


class RecordingTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    channel_count: int = Field(ge=1, le=64)
    channel_names: list[str] = Field(default_factory=list)
    sample_rate: int = Field(default=48000)
    bit_depth: int = Field(default=24)
    codec: str = Field(default="pcm_s24le")
    container: str = Field(default="wav")
    channel_source_defaults: list[ChannelSourceDefault] = Field(default_factory=list)
    metadata_defaults: dict = Field(default_factory=dict)
    filename_pattern: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def pad_channel_names(self) -> "RecordingTemplateCreate":
        while len(self.channel_names) < self.channel_count:
            self.channel_names.append(f"Ch {len(self.channel_names) + 1}")
        self.channel_names = self.channel_names[: self.channel_count]
        return self


class RecordingTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    channel_count: int | None = Field(default=None, ge=1, le=64)
    channel_names: list[str] | None = None
    sample_rate: int | None = None
    bit_depth: int | None = None
    codec: str | None = None
    container: str | None = None
    channel_source_defaults: list[ChannelSourceDefault] | None = None
    metadata_defaults: dict | None = None
    filename_pattern: str | None = Field(default=None, max_length=128)


class RecordingTemplateOut(BaseModel):
    id: int
    name: str
    channel_count: int
    channel_names: list
    sample_rate: int
    bit_depth: int
    codec: str
    container: str
    channel_source_defaults: list
    metadata_defaults: dict
    filename_pattern: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
