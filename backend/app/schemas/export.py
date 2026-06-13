from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from ..models.export import ExportStatus


# Supported export presets exposed to the UI
EXPORT_PRESETS = [
    {"id": "wav_24", "label": "WAV 24-bit (lossless)", "codec": "pcm_s24le", "container": "wav"},
    {"id": "wav_16", "label": "WAV 16-bit (lossless)", "codec": "pcm_s16le", "container": "wav"},
    {"id": "flac",   "label": "FLAC (lossless)",        "codec": "flac",      "container": "flac"},
    {"id": "mp3_320","label": "MP3 320 kbps",            "codec": "libmp3lame","container": "mp3"},
    {"id": "aac_256","label": "AAC 256 kbps",            "codec": "aac",       "container": "m4a"},
]

# FFmpeg format name for each container
CONTAINER_FORMAT = {
    "wav": "wav",
    "flac": "flac",
    "mp3": "mp3",
    "m4a": "ipod",
    "aiff": "aiff",
}

CONTAINER_EXT = {
    "wav": ".wav",
    "flac": ".flac",
    "mp3": ".mp3",
    "m4a": ".m4a",
    "aiff": ".aif",
}


class ExportJobCreate(BaseModel):
    codec: str = Field(..., min_length=1, max_length=32)
    container: str = Field(..., min_length=1, max_length=16)
    channel_selection: list[int] = Field(default_factory=list)
    interleaved: bool = False

    @model_validator(mode="after")
    def validate_container(self) -> "ExportJobCreate":
        if self.container not in CONTAINER_FORMAT:
            raise ValueError(f"Unsupported container '{self.container}'. Use one of: {list(CONTAINER_FORMAT)}")
        return self


class ExportJobOut(BaseModel):
    id: int
    recording_id: int
    codec: str
    container: str
    channel_selection: list[int]
    interleaved: bool
    output_path: str | None
    status: ExportStatus
    progress_pct: float
    error_message: str | None
    celery_task_id: str | None
    created_by: int | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
