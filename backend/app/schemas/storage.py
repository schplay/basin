from datetime import datetime

from pydantic import BaseModel, Field

from ..models.storage import DestinationType, RelocationStatus


class StorageDestinationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    destination_type: DestinationType
    # Local
    local_path: str | None = None
    # Network shared
    network_host: str | None = None
    network_share: str | None = None
    network_interface: str | None = None
    mount_point: str | None = Field(default="/mnt/basin-storage", max_length=256)
    # SMB-specific
    smb_username: str | None = None
    smb_password: str | None = None   # plaintext on the way in; never returned
    smb_domain: str | None = None
    smb_version: str | None = Field(default="3.0", max_length=8)
    # NFS-specific
    nfs_version: str | None = Field(default="4", max_length=4)
    nfs_options: str | None = None


class StorageDestinationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    local_path: str | None = None
    network_host: str | None = None
    network_share: str | None = None
    network_interface: str | None = None
    mount_point: str | None = None
    smb_username: str | None = None
    smb_password: str | None = None
    smb_domain: str | None = None
    smb_version: str | None = None
    nfs_version: str | None = None
    nfs_options: str | None = None
    is_active: bool | None = None


class StorageDestinationOut(BaseModel):
    id: int
    name: str
    destination_type: DestinationType
    is_active: bool
    local_path: str | None
    # Network
    network_host: str | None
    network_share: str | None
    network_interface: str | None
    mount_point: str | None
    smb_username: str | None
    smb_domain: str | None
    smb_version: str | None
    nfs_version: str | None
    nfs_options: str | None
    # Derived
    is_mounted: bool = False
    # Speed test history
    last_speed_test_at: datetime | None
    last_speed_test_write_mbps: float | None
    last_speed_test_read_mbps: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CapacityInfo(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    used_pct: float


class SafeSetting(BaseModel):
    channels: int
    sample_rate: int
    required_mbps: float
    load_pct: float
    safe: bool
    marginal: bool
    over_limit: bool


class SpeedTestResult(BaseModel):
    write_mbps: float
    read_mbps: float
    safe_settings: list[SafeSetting]


class ConnectionTestResult(BaseModel):
    ok: bool
    detail: str


# ── Relocation ────────────────────────────────────────────────────────────────

class RelocationCreate(BaseModel):
    from_destination_id: int
    to_destination_id: int
    delete_source: bool = True


class RelocationOut(BaseModel):
    id: int
    from_destination_id: int
    to_destination_id: int
    status: RelocationStatus
    files_total: int
    files_moved: int
    bytes_total: int
    bytes_moved: int
    celery_task_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
