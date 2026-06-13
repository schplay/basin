from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import require_admin
from ..models.storage import DestinationType, StorageDestination, StorageRelocation, RelocationStatus
from ..schemas.storage import (
    CapacityInfo,
    ConnectionTestResult,
    RelocationCreate,
    RelocationOut,
    SpeedTestResult,
    StorageDestinationCreate,
    StorageDestinationOut,
    StorageDestinationUpdate,
)
from ..services.storage import network as net_svc
from ..services.storage.encryption import encrypt_password
from ..services.storage.manager import (
    compute_safe_settings,
    get_capacity,
    run_speed_test,
    validate_local_path,
)
from ..tasks.relocate import relocate_files

router = APIRouter(prefix="/api/storage", tags=["storage"])

_NETWORK_TYPES = {DestinationType.network_smb, DestinationType.network_nfs}


async def _get_dest_or_404(dest_id: int, session: AsyncSession) -> StorageDestination:
    dest = await session.get(StorageDestination, dest_id)
    if not dest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
    return dest


def _effective_path(dest: StorageDestination) -> str:
    if dest.destination_type in _NETWORK_TYPES:
        return dest.mount_point or "/mnt/basin-storage"
    if dest.local_path:
        return dest.local_path
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Destination has no path configured")


def _to_out(dest: StorageDestination, is_mounted: bool = False) -> StorageDestinationOut:
    out = StorageDestinationOut.model_validate(dest)
    out.is_mounted = is_mounted
    return out


# ── Destinations ─────────────────────────────────────────────────────────────

@router.get("/destinations", response_model=list[StorageDestinationOut])
async def list_destinations(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    result = await session.execute(select(StorageDestination).order_by(StorageDestination.created_at))
    return [StorageDestinationOut.model_validate(d) for d in result.scalars()]


@router.post("/destinations", response_model=StorageDestinationOut, status_code=status.HTTP_201_CREATED)
async def create_destination(
    body: StorageDestinationCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    if body.destination_type in (DestinationType.local_os, DestinationType.local_volume):
        if not body.local_path:
            raise HTTPException(status_code=422, detail="local_path required for local destinations")
        try:
            validate_local_path(body.local_path)
        except (PermissionError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if body.destination_type in _NETWORK_TYPES:
        if not body.network_host or not body.network_share:
            raise HTTPException(status_code=422, detail="network_host and network_share required for network destinations")

    # Build ORM kwargs: exclude the plaintext password field (not a DB column)
    # and exclude None values so ORM defaults are preserved
    data = {k: v for k, v in body.model_dump(exclude={"smb_password"}).items() if v is not None}
    if body.smb_password:
        data["smb_password_enc"] = encrypt_password(body.smb_password)

    dest = StorageDestination(**data)
    session.add(dest)
    await session.flush()
    return StorageDestinationOut.model_validate(dest)


@router.get("/destinations/{dest_id}", response_model=StorageDestinationOut)
async def get_destination(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    mounted = False
    if dest.destination_type in _NETWORK_TYPES and dest.mount_point:
        mounted = await net_svc.is_mounted(dest.mount_point)
    return _to_out(dest, mounted)


@router.put("/destinations/{dest_id}", response_model=StorageDestinationOut)
async def update_destination(
    dest_id: int,
    body: StorageDestinationUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    updates = body.model_dump(exclude_unset=True, exclude={"smb_password"})
    for field, value in updates.items():
        setattr(dest, field, value)
    if body.smb_password is not None:
        dest.smb_password_enc = encrypt_password(body.smb_password)
    await session.flush()
    return StorageDestinationOut.model_validate(dest)


@router.post("/destinations/{dest_id}/activate", response_model=StorageDestinationOut)
async def activate_destination(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)

    # Network destinations must be mounted before activating
    if dest.destination_type in _NETWORK_TYPES:
        if not await net_svc.is_mounted(dest.mount_point or ""):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mount the network share before activating it",
            )

    all_result = await session.execute(
        select(StorageDestination).where(StorageDestination.is_active == True)
    )
    for other in all_result.scalars():
        other.is_active = False

    dest.is_active = True
    await session.flush()
    return StorageDestinationOut.model_validate(dest)


@router.get("/destinations/{dest_id}/capacity", response_model=CapacityInfo)
async def destination_capacity(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    path = _effective_path(dest)
    try:
        return CapacityInfo(**get_capacity(path))
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/destinations/{dest_id}/test", response_model=SpeedTestResult)
async def speed_test(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    path = _effective_path(dest)

    try:
        write_mbps, read_mbps = await run_speed_test(path)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    dest.last_speed_test_at = datetime.now(timezone.utc)
    dest.last_speed_test_write_mbps = write_mbps
    dest.last_speed_test_read_mbps = read_mbps

    return SpeedTestResult(
        write_mbps=write_mbps,
        read_mbps=read_mbps,
        safe_settings=compute_safe_settings(write_mbps),
    )


# ── Network-only endpoints ────────────────────────────────────────────────────

@router.post("/destinations/{dest_id}/mount", response_model=StorageDestinationOut)
async def mount_destination(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    if dest.destination_type not in _NETWORK_TYPES:
        raise HTTPException(status_code=400, detail="Only network destinations can be mounted")
    try:
        await net_svc.mount(dest)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_out(dest, is_mounted=True)


@router.post("/destinations/{dest_id}/umount", response_model=StorageDestinationOut)
async def umount_destination(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    if dest.destination_type not in _NETWORK_TYPES:
        raise HTTPException(status_code=400, detail="Only network destinations can be unmounted")
    if dest.is_active:
        raise HTTPException(status_code=409, detail="Deactivate the destination before unmounting")
    try:
        await net_svc.umount(dest.mount_point or "/mnt/basin-storage")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_out(dest, is_mounted=False)


@router.post("/destinations/{dest_id}/test-connection", response_model=ConnectionTestResult)
async def test_connection(
    dest_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    dest = await _get_dest_or_404(dest_id, session)
    if dest.destination_type not in _NETWORK_TYPES:
        raise HTTPException(status_code=400, detail="Only network destinations support connection tests")
    result = await net_svc.test_connection(dest)
    return ConnectionTestResult(**result)


# ── Relocations ───────────────────────────────────────────────────────────────

@router.get("/relocations", response_model=list[RelocationOut])
async def list_relocations(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    result = await session.execute(
        select(StorageRelocation).order_by(StorageRelocation.created_at.desc())
    )
    return [RelocationOut.model_validate(r) for r in result.scalars()]


@router.post("/relocations", response_model=RelocationOut, status_code=status.HTTP_201_CREATED)
async def create_relocation(
    body: RelocationCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    if body.from_destination_id == body.to_destination_id:
        raise HTTPException(status_code=422, detail="Source and destination must differ")

    src = await session.get(StorageDestination, body.from_destination_id)
    dst = await session.get(StorageDestination, body.to_destination_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source destination not found")
    if not dst:
        raise HTTPException(status_code=404, detail="Target destination not found")

    # Check target network destinations are mounted
    if dst.destination_type in _NETWORK_TYPES:
        if not await net_svc.is_mounted(dst.mount_point or ""):
            raise HTTPException(status_code=409, detail="Target network share is not mounted")

    reloc = StorageRelocation(
        from_destination_id=body.from_destination_id,
        to_destination_id=body.to_destination_id,
        status=RelocationStatus.pending,
    )
    session.add(reloc)
    await session.flush()
    await session.refresh(reloc)

    # Fire Celery task
    task = relocate_files.delay(reloc.id, body.delete_source)
    reloc.celery_task_id = task.id
    await session.flush()

    return RelocationOut.model_validate(reloc)


@router.get("/relocations/{reloc_id}", response_model=RelocationOut)
async def get_relocation(
    reloc_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    reloc = await session.get(StorageRelocation, reloc_id)
    if not reloc:
        raise HTTPException(status_code=404, detail="Relocation not found")
    return RelocationOut.model_validate(reloc)


@router.delete("/relocations/{reloc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_relocation(
    reloc_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_admin),
):
    reloc = await session.get(StorageRelocation, reloc_id)
    if not reloc:
        raise HTTPException(status_code=404, detail="Relocation not found")
    if reloc.status != RelocationStatus.pending:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a relocation in '{reloc.status.value}' state")
    await session.delete(reloc)
