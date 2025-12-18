# Tezaver Bulut - Timeframe Aggregator Tests
"""
Tests for TimeframeAggregator aggregation logic.
"""

from datetime import datetime, timedelta, timezone
from tezaver.bulut.schemas.bar_v1 import BarV1
from tezaver.bulut.services.timeframe_aggregator import TimeframeAggregator

def _create_bar(ts: datetime, o=10, h=12, l=8, c=11, v=100) -> BarV1:
    return BarV1(
        symbol="BTCUSDT",
        tf="15m",
        open_ts=ts,
        close_ts=ts + timedelta(minutes=15),
        o=o, h=h, l=l, c=c, v=v, is_closed=True
    )

def test_derive_1h_basic():
    """Derive 1h bar from 4 consecutive 15m bars."""
    start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    bars = []
    # 10:00 -> 10:15
    bars.append(_create_bar(start, o=100, h=105, l=95, c=102, v=10))
    # 10:15 -> 10:30
    bars.append(_create_bar(start + timedelta(minutes=15), o=102, h=110, l=101, c=108, v=20))
    # 10:30 -> 10:45
    bars.append(_create_bar(start + timedelta(minutes=30), o=108, h=109, l=100, c=105, v=15))
    # 10:45 -> 11:00
    bars.append(_create_bar(start + timedelta(minutes=45), o=105, h=106, l=98, c=101, v=25))
    
    derived = TimeframeAggregator.derive("BTCUSDT", bars)
    b1h = derived["1h"]
    
    assert b1h is not None
    assert b1h.tf == "1h"
    assert b1h.open_ts == start
    assert b1h.close_ts == start + timedelta(minutes=60)
    assert b1h.o == 100 # First open
    assert b1h.h == 110 # Max high
    assert b1h.l == 95  # Min low
    assert b1h.c == 101 # Last close
    assert b1h.v == 70  # Sum volume

def test_derive_insufficient():
    """Should yield None if insufficient bars."""
    start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    bars = [_create_bar(start)]
    
    derived = TimeframeAggregator.derive("BTCUSDT", bars)
    assert derived["1h"] is None
    assert derived["4h"] is None

def test_derive_gap():
    """Should fail if gap exists."""
    start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    bars = []
    bars.append(_create_bar(start)) # 10:00
    bars.append(_create_bar(start + timedelta(minutes=30))) # 10:30 (GAP!)
    bars.append(_create_bar(start + timedelta(minutes=45)))
    bars.append(_create_bar(start + timedelta(minutes=60)))
    
    derived = TimeframeAggregator.derive("BTCUSDT", bars)
    assert derived["1h"] is None
