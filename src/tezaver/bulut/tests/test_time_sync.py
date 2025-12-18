# Tezaver Bulut - Time Sync Tests
"""
Tests for Time Sync Service and Safety Guard (v0.13).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import time
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.time_sync import TimeSyncService
from tezaver.bulut.services.safety_guard import SafetyGuard

@pytest.fixture
def config():
    return BulutConfig(
        time_sync_enabled=True,
        time_sync_max_skew_ms=1000,
        block_execution_if_time_sync_fail=True,
        execution_enabled=True,
        mode="REAL_TESTNET",
        require_arm=False
    )

@pytest.fixture
def telemetry():
    return MagicMock()

@pytest.fixture
def time_sync(config, telemetry):
    service = TimeSyncService(config, telemetry)
    return service

import asyncio

def test_time_sync_logic(time_sync):
    """Test offset calculation."""
    async def run():
        # Mock aiohttp
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json.return_value = {"serverTime": int(time.time() * 1000) + 500}
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            await time_sync.refresh()
            
            # approximate offset should be around 500
            assert 400 < time_sync._offset_ms < 600
            
            # now_ms should use offset
            local_now = int(time.time() * 1000)
            corrected = time_sync.now_ms()
            assert corrected > local_now + 400
            
    asyncio.run(run())

def test_skew_fail(time_sync, config):
    """Test skew too high."""
    async def run():
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            # Huge skew +2000m
            mock_resp.json.return_value = {"serverTime": int(time.time() * 1000) + 2000}
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            await time_sync.refresh()
            
            healthy, details = time_sync.is_healthy()
            assert not healthy
            assert details["reason"] == "SKEW_TOO_HIGH"
            
    asyncio.run(run())

def test_safety_guard_block(config):
    """Test Safety Guard blocks execution if time sync unhealthy."""
    ctx = MagicMock()
    ctx.config = config
    # Set attributes directly on Mock ctx.state (which is a Mock unless specified)
    # ctx.state is a Mock.
    ctx.state.trade_locked = False
    ctx.state.pattern_pack_loaded = True
    
    # 1. Unhealthy Time Sync
    mock_ts = MagicMock()
    mock_ts.is_healthy.return_value = (False, {})
    ctx.time_sync = mock_ts
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert not allowed
    assert reason == "TIME_SYNC_UNHEALTHY"
    
    # 2. Healthy
    mock_ts.is_healthy.return_value = (True, {})
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert allowed
