# Tezaver Bulut - Dual Budget Tests
"""
Tests for Dual Budget Governor and Configurable Weights.
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from tezaver.bulut.services.rate_limit_governor import RateLimitGovernor
from tezaver.bulut.core.config import BulutConfig

@pytest.fixture
def dual_config():
    return BulutConfig(
        rate_limit_enabled=True,
        rate_limit_budget_market_per_min=100,
        rate_limit_budget_trade_per_min=20,
        rate_limit_safety_pct=1.0, # Simple math
        endpoint_weights={
            "GET:/market": 1,
            "POST:/order": 2
        }
    )

def test_dual_budget_separation(dual_config):
    """Verify MARKET and TRADE buckets are separate."""
    async def run():
        gov = RateLimitGovernor(dual_config)
        
        # 1. Spend Market
        await gov.acquire("MARKET", "GET:/market") # Weight 1
        assert gov._used_market == 1
        assert gov._used_trade == 0
        
        # 2. Spend Trade
        await gov.acquire("TRADE", "POST:/order") # Weight 2
        assert gov._used_market == 1
        assert gov._used_trade == 2
        
        # 3. Verify Unknown
        await gov.acquire("MARKET", "GET:/unknown") # Default 10
        assert gov._used_market == 11
        
    asyncio.run(run())

def test_unknown_weight(dual_config):
    """Verify unknown endpoint gets penalty weight."""
    async def run():
        gov = RateLimitGovernor(dual_config)
        await gov.acquire("MARKET", "WTF:/endpoint")
        assert gov._used_market == 10
        
    asyncio.run(run())
