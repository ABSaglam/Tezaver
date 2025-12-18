# Tezaver Bulut - Rate Limit Governor Tests
"""
Tests for Rate Limit Governor logic (budget, sleep, backoff).
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock

from tezaver.bulut.services.rate_limit_governor import RateLimitGovernor
from tezaver.bulut.core.config import BulutConfig

@pytest.fixture
def mock_telemetry():
    return MagicMock()

@pytest.fixture
def config():
    return BulutConfig(
        rate_limit_enabled=True,
        rate_limit_budget_per_min=10,
        rate_limit_safety_pct=0.8
    )

def test_governor_budget_acquire(config, mock_telemetry):
    """Test that governor tracks usage and eventually throttles (mock sleep)."""
    async def run_test():
        gov = RateLimitGovernor(config, mock_telemetry)
        
        # 80% of 10 = 8 safety limit
        
        # 1. Acquire 5 (OK)
        await gov.acquire(5)
        assert gov._used_weight == 5
        
        # 2. Acquire 2 (OK, total 7 < 8)
        await gov.acquire(2)
        assert gov._used_weight == 7
        
        # 3. Acquire 2 (Breach 8? 7+2=9 > 8) -> Should Sleep
        # We patch asyncio.sleep to verify call
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gov.acquire(2)
            
            # Should have called sleep
            mock_sleep.assert_called_once()
            # Sleep duration should be around 60s
            args = mock_sleep.call_args[0]
            assert 50.0 < args[0] < 61.0
            
            # After sleep, window reset?
            # Our logic forces reset after sleep
            # used_weight should be 0, then +2 = 2
            assert gov._used_weight == 2

    asyncio.run(run_test())

def test_backoff_logic(config, mock_telemetry):
    """Test exponential backoff calculations."""
    async def run_test():
        gov = RateLimitGovernor(config, mock_telemetry)
        
        # Attempt 1
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gov.handle_backoff(1, "429")
            
            # Base 250ms * 2^1 = 500ms
            # Jitter 0.8-1.2 => 400-600ms
            args = mock_sleep.call_args[0]
            sleep_sec = args[0] # seconds
            assert 0.4 <= sleep_sec <= 0.6
            
        # Attempt 3
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gov.handle_backoff(3, "429")
            
            # Base 250ms * 2^3 = 2000ms
            # Jitter => 1.6s - 2.4s
            args = mock_sleep.call_args[0]
            sleep_sec = args[0]
            assert 1.6 <= sleep_sec <= 2.4
            
    asyncio.run(run_test())

def test_window_reset_telemetry(config, mock_telemetry):
    """Test standard window reset without locking (sync Check)."""
    gov = RateLimitGovernor(config, mock_telemetry)
    gov._used_weight = 5
    
    # Move time forward 61s
    gov._window_start = time.time() - 61
    
    gov._reset_window_if_needed()
    
    assert gov._used_weight == 0
    mock_telemetry.emit_request_budget.assert_called_once()
