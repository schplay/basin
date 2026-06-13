"""Async UDP OSC client for Behringer X32 and Wing consoles.

Queries are fire-and-wait: we send one or more OSC messages and collect replies
on the same bound socket until all expected addresses arrive or a timeout fires.
"""
from __future__ import annotations

import asyncio
import socket
import time
from typing import Any

from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

from ...models.console import ConsoleType

# X32: 32 mono channels on /ch/XX/config/name
_X32_CH_FMT = "/ch/{:02d}/config/name"
# Wing: up to 40 mono channels on /ch/X/name
_WING_CH_FMT = "/ch/{}/name"

# Default ports per console type
DEFAULT_PORT: dict[ConsoleType, int] = {
    ConsoleType.behringer_x32: 10023,
    ConsoleType.behringer_wing: 2223,
}


def _encode(address: str, *args: Any) -> bytes:
    builder = OscMessageBuilder(address=address)
    for a in args:
        builder.add_arg(a)
    return builder.build().dgram


class _CollectorProtocol(asyncio.DatagramProtocol):
    """Collects OSC datagrams matching a set of expected addresses."""

    def __init__(self, expected: set[str], future: asyncio.Future[dict[str, Any]]):
        self._expected = set(expected)
        self._results: dict[str, Any] = {}
        self._future = future

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            msg = OscMessage(dgram=data)
        except Exception:
            return
        if msg.address not in self._expected:
            return
        val = msg.params[0] if msg.params else ""
        self._results[msg.address] = val
        if self._results.keys() >= self._expected and not self._future.done():
            self._future.set_result(dict(self._results))

    def error_received(self, exc: Exception) -> None:
        if not self._future.done():
            self._future.set_exception(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        if not self._future.done():
            self._future.set_result(dict(self._results))


async def _batch_query(
    ip: str,
    port: int,
    addresses: list[str],
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Send each address as an OSC query and collect all replies."""
    loop = asyncio.get_event_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    protocol_factory = lambda: _CollectorProtocol(set(addresses), future)

    transport, _ = await loop.create_datagram_endpoint(
        protocol_factory,
        local_addr=("0.0.0.0", 0),
        family=socket.AF_INET,
    )
    try:
        for addr in addresses:
            transport.sendto(_encode(addr), (ip, port))
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
    except asyncio.TimeoutError:
        # Return whatever we collected before timeout
        if not future.done():
            future.cancel()
        return {}
    finally:
        transport.close()


async def ping(ip: str, port: int, timeout: float = 2.0) -> float | None:
    """Send /xinfo (X32) or /ping and return round-trip latency in ms, or None on failure."""
    loop = asyncio.get_event_loop()
    future: asyncio.Future[float] = loop.create_future()
    sent_at = time.monotonic()

    class _PingProtocol(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            if not future.done():
                future.set_result((time.monotonic() - sent_at) * 1000.0)

        def error_received(self, exc):
            if not future.done():
                future.set_exception(exc)

        def connection_lost(self, exc):
            if not future.done():
                future.cancel()

    transport, _ = await loop.create_datagram_endpoint(
        _PingProtocol,
        local_addr=("0.0.0.0", 0),
        family=socket.AF_INET,
    )
    try:
        # /xinfo works on both X32 and Wing; fallback is a basic packet
        transport.sendto(_encode("/xinfo"), (ip, port))
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        return None
    finally:
        transport.close()


async def get_channel_names(
    ip: str,
    port: int,
    console_type: ConsoleType,
    channel_count: int,
    timeout: float = 5.0,
) -> list[str]:
    """Fetch channel names from the console.

    Returns a list of *channel_count* strings (empty string for any that timed out).
    """
    max_ch = 32 if console_type == ConsoleType.behringer_x32 else 40
    count = min(channel_count, max_ch)
    fmt = _X32_CH_FMT if console_type == ConsoleType.behringer_x32 else _WING_CH_FMT

    addresses = [fmt.format(i) for i in range(1, count + 1)]
    results = await _batch_query(ip, port, addresses, timeout=timeout)

    return [str(results.get(addr, "")) for addr in addresses]
