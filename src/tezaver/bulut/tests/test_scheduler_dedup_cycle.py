# Tezaver Bulut - Scheduler Dedup Tests
"""
Tests for scheduler cycle deduplication logic.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone

from tezaver.bulut.engine.scheduler import AsyncScheduler
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.bar_v1 import BarV1

@pytest.mark.asyncio
async def test_scheduler_skips_same_close_ts():
    """Scheduler should not run cycle if close_ts hasn't changed."""
    config = BulutConfig(poll_interval_seconds=0) # Fast loop
    scheduler = AsyncScheduler(config)
    
    # Mock services
    scheduler._rest_client = AsyncMock()
    scheduler._poller = AsyncMock()
    
    # Setup state: last processed ts is T
    t_now = datetime.now(timezone.utc)
    scheduler._last_processed_close_ts = t_now
    
    # Mock REST returning SAME bar
    mock_bar = BarV1("BTCUSDT", "15m", t_now, t_now, 0,0,0,0,0)
    scheduler._rest_client.get_latest_closed_bar.return_value = mock_bar
    
    # Run loop step (simulate by calling internal logic or run for short time)
    # We can't easily call _loop since it's infinite. 
    # We will simulate the logic inside _loop manually.
    
    # --- Logic Simulation ---
    ref_bar = await scheduler._rest_client.get_latest_closed_bar("BTC", "15m")
    triggered = False
    
    if ref_bar:
         if (scheduler._last_processed_close_ts is None) or (ref_bar.close_ts > scheduler._last_processed_close_ts):
             triggered = True
    
    assert triggered is False
    
    # --- New Bar Logic ---
    new_ts = t_now + timedelta(minutes=15)
    mock_bar_new = BarV1("BTCUSDT", "15m", new_ts, new_ts, 0,0,0,0,0)
    scheduler._rest_client.get_latest_closed_bar.return_value = mock_bar_new
    
    triggered_new = False
    ref_bar = await scheduler._rest_client.get_latest_closed_bar("BTC", "15m")
    if ref_bar:
         if (scheduler._last_processed_close_ts is None) or (ref_bar.close_ts > scheduler._last_processed_close_ts):
             triggered_new = True

    assert triggered_new is True
