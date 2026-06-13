"""Network share mount/umount helpers (SMB via CIFS, NFS).

All operations shell out to the Linux mount/umount commands.  The appliance
process must have the necessary sudo rights or run as root.

All public functions are async; blocking subprocess calls are dispatched to the
default thread-pool executor so they don't stall the event loop.
"""
from __future__ import annotations

import asyncio
import shlex
import subprocess
from pathlib import Path

from ...models.storage import DestinationType, StorageDestination
from .encryption import decrypt_password


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ── Mount ─────────────────────────────────────────────────────────────────────

def _mount_cmd(dest: StorageDestination) -> list[str]:
    mp = dest.mount_point or "/mnt/basin-storage"

    if dest.destination_type == DestinationType.network_smb:
        password = decrypt_password(dest.smb_password_enc) if dest.smb_password_enc else ""
        opts = [
            f"username={dest.smb_username or 'guest'}",
            f"password={password}",
            f"vers={dest.smb_version or '3.0'}",
            "iocharset=utf8",
            "dir_mode=0775",
            "file_mode=0664",
        ]
        if dest.smb_domain:
            opts.append(f"domain={dest.smb_domain}")
        if dest.network_interface:
            opts.append(f"bindif={dest.network_interface}")
        return [
            "mount", "-t", "cifs",
            f"//{dest.network_host}/{dest.network_share}",
            mp,
            "-o", ",".join(opts),
        ]

    if dest.destination_type == DestinationType.network_nfs:
        opts = [f"vers={dest.nfs_version or '4'}", "rw"]
        if dest.nfs_options:
            opts.extend(dest.nfs_options.split(","))
        return [
            "mount", "-t", "nfs",
            f"{dest.network_host}:{dest.network_share}",
            mp,
            "-o", ",".join(opts),
        ]

    raise ValueError(f"Not a network destination type: {dest.destination_type}")


def _is_mounted_sync(mount_point: str) -> bool:
    try:
        result = _run(["mountpoint", "-q", mount_point], timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _mount_sync(dest: StorageDestination) -> None:
    mp = dest.mount_point or "/mnt/basin-storage"
    Path(mp).mkdir(parents=True, exist_ok=True)

    if _is_mounted_sync(mp):
        return  # Already mounted — idempotent

    cmd = _mount_cmd(dest)
    result = _run(cmd, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"mount failed: {result.stderr.strip()}")


def _umount_sync(mount_point: str) -> None:
    if not _is_mounted_sync(mount_point):
        return  # Not mounted — idempotent
    result = _run(["umount", mount_point], timeout=15)
    if result.returncode != 0:
        result_lazy = _run(["umount", "-l", mount_point], timeout=15)
        if result_lazy.returncode != 0:
            raise RuntimeError(f"umount failed: {result.stderr.strip()}")


def _test_smb_sync(dest: StorageDestination, timeout: int = 10) -> dict:
    password = decrypt_password(dest.smb_password_enc) if dest.smb_password_enc else ""
    user_arg = f"{dest.smb_username or 'guest'}%{password}"
    cmd = [
        "smbclient",
        f"//{dest.network_host}/{dest.network_share}",
        "-U", user_arg,
        "-c", "ls",
        "--no-pass" if not password else "",
    ]
    cmd = [c for c in cmd if c]  # remove empty strings
    try:
        result = _run(cmd, timeout=timeout)
        if result.returncode == 0:
            return {"ok": True, "detail": "Connection successful"}
        return {"ok": False, "detail": result.stderr.strip() or "smbclient failed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "Connection timed out"}
    except FileNotFoundError:
        return {"ok": False, "detail": "smbclient not installed on appliance"}


def _test_nfs_sync(dest: StorageDestination, timeout: int = 10) -> dict:
    cmd = ["showmount", "-e", dest.network_host]
    try:
        result = _run(cmd, timeout=timeout)
        if result.returncode == 0:
            return {"ok": True, "detail": f"NFS exports available on {dest.network_host}"}
        return {"ok": False, "detail": result.stderr.strip() or "showmount failed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "Connection timed out"}
    except FileNotFoundError:
        return {"ok": False, "detail": "showmount not installed on appliance"}


# ── Async public API ──────────────────────────────────────────────────────────

async def mount(dest: StorageDestination) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _mount_sync, dest)


async def umount(mount_point: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _umount_sync, mount_point)


async def is_mounted(mount_point: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _is_mounted_sync, mount_point)


async def test_connection(dest: StorageDestination) -> dict:
    loop = asyncio.get_event_loop()
    if dest.destination_type == DestinationType.network_smb:
        return await loop.run_in_executor(None, _test_smb_sync, dest, 10)
    if dest.destination_type == DestinationType.network_nfs:
        return await loop.run_in_executor(None, _test_nfs_sync, dest, 10)
    raise ValueError(f"Not a network destination: {dest.destination_type}")
