from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import require_admin
from ..schemas.network import NetworkConfigApply, NetworkInterface
from ..services.network import apply_interface_config, get_interfaces

router = APIRouter(prefix="/api/network", tags=["network"])


@router.get("/interfaces", response_model=list[NetworkInterface])
async def list_interfaces(_=Depends(require_admin)):
    return get_interfaces()


@router.put("/interfaces/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def configure_interface(
    name: str,
    body: NetworkConfigApply,
    _=Depends(require_admin),
):
    try:
        await apply_interface_config(
            interface=name,
            address=body.address,
            prefix=body.prefix,
            gateway=body.gateway,
            dns=body.dns,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
