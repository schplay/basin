"""Network interface queries and configuration via the privileged netplan helper."""
import asyncio
import json
import socket
import struct
from typing import Any

import netifaces


def _netmask_to_prefix(netmask: str) -> int:
    packed = socket.inet_aton(netmask)
    return bin(struct.unpack("!I", packed)[0]).count("1")


def get_interfaces() -> list[dict[str, Any]]:
    result = []
    for name in netifaces.interfaces():
        addrs = netifaces.ifaddresses(name)
        ipv4 = addrs.get(netifaces.AF_INET, [{}])[0]
        mac_entry = addrs.get(netifaces.AF_LINK, [{}])[0]

        ip = ipv4.get("addr")
        netmask = ipv4.get("netmask")
        prefix = _netmask_to_prefix(netmask) if netmask else None

        result.append(
            {
                "name": name,
                "ip": ip,
                "prefix": prefix,
                "mac": mac_entry.get("addr"),
                "is_up": ip is not None,
            }
        )
    return result


async def apply_interface_config(
    interface: str,
    address: str,
    prefix: int,
    gateway: str | None,
    dns: list[str],
) -> None:
    """Write static IP config via the privileged netplan helper."""
    payload = json.dumps(
        {
            "interface": interface,
            "address": address,
            "prefix": prefix,
            "gateway": gateway or "",
            "dns": dns,
        }
    ).encode()

    proc = await asyncio.create_subprocess_exec(
        "sudo",
        "/usr/local/bin/basin-netplan-helper",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=payload)
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "netplan-helper returned non-zero exit code")
