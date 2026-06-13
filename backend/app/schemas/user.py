from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..models.user import UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.operator


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=64)
    password: str | None = Field(default=None, min_length=8)
    role: UserRole | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    group_ids: list[int] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _extract_group_ids(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        try:
            group_ids = [g.id for g in (data.group_access or [])]
        except Exception:
            group_ids = []
        return {
            "id": data.id,
            "username": data.username,
            "role": data.role,
            "is_active": data.is_active,
            "group_ids": group_ids,
        }


class UserGroupAssignment(BaseModel):
    group_ids: list[int]
