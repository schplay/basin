from datetime import datetime

from pydantic import BaseModel, Field


class RecordingGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None
    default_template_id: int | None = None


class RecordingGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: int | None = None
    default_template_id: int | None = None


class RecordingGroupOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    filesystem_path: str
    default_template_id: int | None
    created_at: datetime
    children: list["RecordingGroupOut"] = []

    model_config = {"from_attributes": True}


RecordingGroupOut.model_rebuild()


class GroupAccessAssignment(BaseModel):
    user_ids: list[int]
