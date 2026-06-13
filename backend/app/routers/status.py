import shutil
import socket
import subprocess
from typing import Any

import netifaces
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_session
from ..models.recording import Recording, RecordingStatus

router = APIRouter(prefix="/api/status", tags=["status"])


def _get_interfaces() -> list[dict[str, Any]]:
    interfaces = []
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        ipv4 = addrs.get(netifaces.AF_INET, [{}])[0].get("addr")
        mac = addrs.get(netifaces.AF_LINK, [{}])[0].get("addr")
        interfaces.append({"name": iface, "ip": ipv4, "mac": mac})
    return interfaces


def _service_status(name: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


@router.get("")
async def system_status(session: AsyncSession = Depends(get_session)):
    active_count_result = await session.execute(
        select(func.count()).select_from(Recording).where(Recording.status == RecordingStatus.recording)
    )
    active_recordings = active_count_result.scalar() or 0

    services = {
        "basin-api": _service_status("basin-api"),
        "basin-worker": _service_status("basin-worker"),
        "basin-aes67": _service_status("basin-aes67"),
        "nginx": _service_status("nginx"),
        "postgresql": _service_status("postgresql"),
        "redis": _service_status("redis"),
    }

    storage_info = None
    try:
        usage = shutil.disk_usage(settings.storage_root)
        storage_info = {
            "path": settings.storage_root,
            "total_gb": round(usage.total / 1e9, 1),
            "used_gb": round(usage.used / 1e9, 1),
            "free_gb": round(usage.free / 1e9, 1),
        }
    except OSError:
        pass

    return {
        "hostname": socket.gethostname(),
        "version": settings.app_version,
        "interfaces": _get_interfaces(),
        "services": services,
        "active_recordings": active_recordings,
        "storage": storage_info,
    }
