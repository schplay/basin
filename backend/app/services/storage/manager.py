"""Local storage destination management and speed testing."""
import asyncio
import os
import shutil
import time
from pathlib import Path

CHANNEL_COUNTS = [8, 16, 24, 32, 48, 64, 96, 128]
SAMPLE_RATES = [44100, 48000, 88200, 96000]
_BIT_DEPTH = 24
_SAFETY_MARGIN = 1.2
_SPEED_TEST_SIZE_MB = 512
_CHUNK_SIZE = 1024 * 1024  # 1 MB


def get_capacity(path: str) -> dict:
    usage = shutil.disk_usage(path)
    used_pct = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
    return {
        # Byte-level (used by dashboard)
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": used_pct,
        # GB-level (used by CapacityInfo schema)
        "total_gb": round(usage.total / 1e9, 2),
        "used_gb": round(usage.used / 1e9, 2),
        "free_gb": round(usage.free / 1e9, 2),
        "used_pct": used_pct,
    }


def compute_safe_settings(write_mbps: float) -> list[dict]:
    rows = []
    for channels in CHANNEL_COUNTS:
        for sample_rate in SAMPLE_RATES:
            required = channels * sample_rate * (_BIT_DEPTH / 8) / 1_000_000 * _SAFETY_MARGIN
            load_pct = (required / write_mbps * 100) if write_mbps > 0 else 9999
            rows.append(
                {
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "required_mbps": round(required, 1),
                    "load_pct": round(load_pct, 0),
                    "safe": load_pct <= 70,
                    "marginal": 70 < load_pct <= 90,
                    "over_limit": load_pct > 90,
                }
            )
    return rows


def _write_test(path: Path, size_mb: int) -> float:
    chunk = os.urandom(_CHUNK_SIZE)
    test_file = path / ".basin_speedtest_tmp"
    try:
        start = time.perf_counter()
        with open(test_file, "wb") as f:
            for _ in range(size_mb):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        return size_mb / (time.perf_counter() - start)
    finally:
        test_file.unlink(missing_ok=True)


def _read_test(path: Path, size_mb: int) -> float:
    chunk = os.urandom(_CHUNK_SIZE)
    test_file = path / ".basin_speedtest_read_tmp"
    try:
        with open(test_file, "wb") as f:
            for _ in range(size_mb):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())

        start = time.perf_counter()
        with open(test_file, "rb") as f:
            while f.read(_CHUNK_SIZE):
                pass
        return size_mb / (time.perf_counter() - start)
    finally:
        test_file.unlink(missing_ok=True)


async def run_speed_test(storage_path: str, size_mb: int = _SPEED_TEST_SIZE_MB) -> tuple[float, float]:
    """Run write then read speed test. Returns (write_mbps, read_mbps)."""
    path = Path(storage_path)
    if not path.is_dir():
        raise FileNotFoundError(f"Storage path does not exist: {storage_path}")

    loop = asyncio.get_event_loop()
    write_mbps = await loop.run_in_executor(None, _write_test, path, size_mb)
    read_mbps = await loop.run_in_executor(None, _read_test, path, size_mb)
    return round(write_mbps, 1), round(read_mbps, 1)


def validate_local_path(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    if not os.access(p, os.W_OK):
        raise PermissionError(f"Path is not writable: {path}")
    return p
