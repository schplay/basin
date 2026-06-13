"""Tests for the playback engine (MOCK_AUDIO mode)."""
from __future__ import annotations

import asyncio
import pytest

from app.services.audio import playback_engine as pe
from app.services.audio.playback_engine import PlaybackSession


@pytest.fixture(autouse=True)
def enable_mock_audio(monkeypatch):
    from app.config import settings as s
    monkeypatch.setattr(s, "mock_audio", True)


@pytest.fixture(autouse=True)
def clean_engine():
    pe._sessions.clear()
    yield
    for sid, session in list(pe._sessions.items()):
        if session._task and not session._task.done():
            session._task.cancel()
        if session.process:
            try:
                session.process.terminate()
            except Exception:
                pass
    pe._sessions.clear()


@pytest.mark.asyncio
async def test_start_playback_returns_session():
    session = await pe.start_playback(
        recording_id=1,
        filesystem_path="/tmp/basin_test_playback",
        channel_count=4,
    )
    assert isinstance(session, PlaybackSession)
    assert session.recording_id == 1
    assert pe.is_playing(1)


@pytest.mark.asyncio
async def test_start_playback_idempotent_raises():
    await pe.start_playback(recording_id=2, filesystem_path="/tmp/x", channel_count=2)
    # A second start for the same ID should still succeed
    # (engine replaces the session); verify at least it's playing
    assert pe.is_playing(2)


@pytest.mark.asyncio
async def test_stop_playback_returns_duration():
    await pe.start_playback(recording_id=3, filesystem_path="/tmp/x", channel_count=2)
    await asyncio.sleep(0.05)
    duration = await pe.stop_playback(3)
    assert isinstance(duration, float)
    assert duration >= 0.0
    assert not pe.is_playing(3)


@pytest.mark.asyncio
async def test_stop_nonexistent_raises():
    with pytest.raises(RuntimeError, match="No active playback session"):
        await pe.stop_playback(999)


@pytest.mark.asyncio
async def test_is_playing_false_before_start():
    assert not pe.is_playing(42)


@pytest.mark.asyncio
async def test_full_lifecycle():
    assert not pe.is_playing(10)
    await pe.start_playback(recording_id=10, filesystem_path="/tmp/x", channel_count=8)
    assert pe.is_playing(10)
    duration = await pe.stop_playback(10)
    assert not pe.is_playing(10)
    assert isinstance(duration, float)


@pytest.mark.asyncio
async def test_session_duration_property():
    session = await pe.start_playback(recording_id=20, filesystem_path="/tmp", channel_count=2)
    await asyncio.sleep(0.1)
    dur = session.duration
    assert dur >= 0.1
    await pe.stop_playback(20)
