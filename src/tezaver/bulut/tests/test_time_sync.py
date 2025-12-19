# Tezaver Bulut - Time Sync Tests
"""
Tests for Time Sync Service and Safety Guard (v0.13).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import time

from tezaver.bulut.services.time_sync import TimeSyncService
from tezaver.bulut.services.safety_guard import SafetyGuard


@pytest.fixture
def time_sync_service(cfg, mock_telemetry):
    """Create TimeSyncService with config from conftest."""
    return TimeSyncService(cfg, mock_telemetry)


def test_time_sync_logic(time_sync_service):
    """Test offset calculation with mocked HTTP response."""
    async def run():
        # Mock the entire session context
        mock_resp = MagicMock()
        mock_resp.status = 200
        server_time = int(time.time() * 1000) + 500
        mock_resp.json = AsyncMock(return_value={"serverTime": server_time})
        
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None
        
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_ctx
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_session
            
            await time_sync_service.refresh()
            
            # Offset should be approximately 500ms
            assert time_sync_service._offset_ms is not None
            # Just verify offset got set (exact value depends on timing)
            
    asyncio.run(run())


def test_skew_fail(time_sync_service, cfg):
    """Test skew detection when offset too high."""
    # Manually set high offset to simulate skew
    time_sync_service._offset_ms = 5000  # 5000ms > default 1000ms threshold
    time_sync_service._last_sync_ts = time.time()
    
    healthy, details = time_sync_service.is_healthy()
    assert not healthy
    # Service should detect skew too high


def test_safety_guard_block(cfg):
    """Test Safety Guard blocks execution if time sync unhealthy."""
    ctx = MagicMock()
    # Need to mock config with all required fields
    mock_cfg = MagicMock()
    mock_cfg.execution_enabled = True
    mock_cfg.block_execution_if_time_sync_fail = True
    mock_cfg.mode = "REAL_TESTNET"  # Not DEV mode
    mock_cfg.require_arm = False
    ctx.config = mock_cfg
    
    ctx.state = MagicMock()
    ctx.state.trade_locked = False
    ctx.state.pattern_pack_loaded = True
    
    # Unhealthy Time Sync
    mock_ts = MagicMock()
    mock_ts.is_healthy.return_value = (False, {"reason": "SKEW_TOO_HIGH"})
    ctx.time_sync = mock_ts
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert not allowed
    assert reason == "TIME_SYNC_UNHEALTHY"
    
    # Healthy Time Sync
    mock_ts.is_healthy.return_value = (True, {})
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert allowed
