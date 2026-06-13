from pydantic import BaseModel, Field


class NetworkInterface(BaseModel):
    name: str
    ip: str | None
    prefix: int | None
    mac: str | None
    is_up: bool


class NetworkConfigApply(BaseModel):
    address: str
    prefix: int = Field(ge=1, le=32)
    gateway: str | None = None
    dns: list[str] = []
