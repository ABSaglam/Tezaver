# Tezaver Bulut - Exit Engine Tests
"""
Tests for Auto Exit logic.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from tezaver.bulut.engine.exit_engine import ExitEngine
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.exit_profile_v1 import ExitProfileV1, ExitRule, ExitScope, DEFAULT_EXIT_PROFILE
from tezaver.bulut.schemas.bar_v1 import BarV1


def test_exit_fixed_pct():
    config = BulutConfig()
    engine = ExitEngine(config)
    
    # Setup Mocks
    persistence = MagicMock()
    bars = MagicMock()
    loader = MagicMock()
    cycle_ts = datetime.now(timezone.utc)
    
    # 1 open position
    persistence.get_open_positions.return_value = [{
        "symbol": "BTC",
        "entry_price": 100.0,
        "entry_ts": (cycle_ts - timedelta(hours=1)).isoformat(),
        "qty": 1.0, "notional_usdt": 100.0,
        "pattern_id": "P1"
    }]
    
    # Current price has dropped 2% -> Stop Loss (1%)
    bars.get_last_closed.return_value = BarV1("BTC", "15m", cycle_ts, cycle_ts, 98, 99, 97, 98, 100)
    
    # Loader returns profile with 1% SL
    profile = ExitProfileV1("test", "v1", 10, [
        ExitRule("fixed_pct", sl_pct=1.0, tp_pct=2.0)
    ])
    loader.resolve.return_value = profile
    
    plans = engine.evaluate_exits(persistence, bars, loader, cycle_ts)
    
    assert len(plans) == 1
    p = plans[0]
    assert p.decision.name == "CLOSE"
    assert "SL_HIT_1.0%" in p.reasons["reason"]


def test_exit_time_stop():
    config = BulutConfig()
    engine = ExitEngine(config)
    
    persistence = MagicMock()
    bars = MagicMock()
    loader = MagicMock()
    cycle_ts = datetime.now(timezone.utc)
    
    # Position open for 20 bars (5 hours)
    entry_ts = cycle_ts - timedelta(minutes=15 * 20)
    
    persistence.get_open_positions.return_value = [{
        "symbol": "BTC",
        "entry_price": 100.0,
        "entry_ts": entry_ts.isoformat(),
        "qty": 1.0, "notional_usdt": 100.0
    }]
    
    # Price unchanged
    bars.get_last_closed.return_value = BarV1("BTC", "15m", cycle_ts, cycle_ts, 100, 100, 100, 100, 100)
    
    # Profile with 16 bar limit
    profile = ExitProfileV1("timetest", "v1", 10, [
        ExitRule("time_stop", max_bars=16)
    ])
    loader.resolve.return_value = profile
    
    plans = engine.evaluate_exits(persistence, bars, loader, cycle_ts)
    
    assert len(plans) == 1
    p = plans[0]
    assert p.decision.name == "CLOSE"
    assert "TIME_STOP_16BARS" in p.reasons["reason"]
