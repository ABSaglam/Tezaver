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
    # BulutConfig is frozen, use defaults
    return BulutConfig()

def test_governor_budget_acquire(config, mock_telemetry):
    """Test that governor tracks usage correctly."""
    async def run_test():
        gov = RateLimitGovernor(config, mock_telemetry)
        
        # Acquire for MARKET channel
        await gov.acquire("MARKET", "GET:/fapi/v1/klines")
        assert gov._used_market > 0
        
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
            assert 0.3 <= sleep_sec <= 0.7  # Wider margin for jitter
            
        # Attempt 3
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await gov.handle_backoff(3, "429")
            
            # Base 250ms * 2^3 = 2000ms
            # Jitter => 1.6s - 2.4s
            args = mock_sleep.call_args[0]
            sleep_sec = args[0]
            assert 1.4 <= sleep_sec <= 2.6  # Wider margin
            
    asyncio.run(run_test())

def test_window_reset_telemetry(config, mock_telemetry):
    """Test standard window reset after 60s."""
    gov = RateLimitGovernor(config, mock_telemetry)
    gov._used_market = 5
    gov._used_trade = 3
    
    # Move time forward 61s
    gov._window_start = time.time() - 61
    
    gov._reset_window_if_needed()
    
    assert gov._used_market == 0
    assert gov._used_trade == 0
    # Telemetry called for both channels
    assert mock_telemetry.emit_request_budget.call_count == 2
