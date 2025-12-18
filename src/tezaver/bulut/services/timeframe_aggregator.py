# Tezaver Bulut - Timeframe Aggregator
"""
Derives higher timeframe (1h, 4h) bars from 15m bars.
"""

from typing import List, Optional, Dict
from datetime import timedelta

from tezaver.bulut.schemas.bar_v1 import BarV1


class TimeframeAggregator:
    """
    Aggregates 15m bars into 1h and 4h bars.
    
    Rules:
    - 1h = 4 x 15m closed bars
    - 4h = 16 x 15m closed bars (4 x 1h)
    """
    
    @staticmethod
    def derive(symbol: str, base_bars_15m: List[BarV1]) -> Dict[str, Optional[BarV1]]:
        """
        Derive 1h and 4h bars from list of 15m bars.
        Expects base_bars_15m to be sorted by time (oldest first).
        Returns {"1h": ..., "4h": ...}
        """
        result = {"1h": None, "4h": None}
        
        if not base_bars_15m:
            return result
            
        # --- Derive 1h ---
        # Need last 4 bars for 1h
        if len(base_bars_15m) >= 4:
            chunk_1h = base_bars_15m[-4:]
            if TimeframeAggregator._is_contiguous(chunk_1h, 15):
                 result["1h"] = TimeframeAggregator._aggregate(symbol, "1h", chunk_1h)

        # --- Derive 4h ---
        # Need last 16 bars for 4h
        if len(base_bars_15m) >= 16:
            chunk_4h = base_bars_15m[-16:]
            if TimeframeAggregator._is_contiguous(chunk_4h, 15):
                result["4h"] = TimeframeAggregator._aggregate(symbol, "4h", chunk_4h)
                
        return result

    @staticmethod
    def _is_contiguous(bars: List[BarV1], interval_minutes: int) -> bool:
        """Check if bars are contiguous in time."""
        if len(bars) < 2:
            return True
            
        expected_delta = timedelta(minutes=interval_minutes)
        for i in range(1, len(bars)):
            prev = bars[i-1]
            curr = bars[i]
            # Gap check: current open should equal previous close (or very strict timing)
            # Simpler check: curr.open_ts - prev.open_ts == interval
            if (curr.open_ts - prev.open_ts) != expected_delta:
                return False
        return True

    @staticmethod
    def _aggregate(symbol: str, target_tf: str, bars: List[BarV1]) -> BarV1:
        """Aggregate list of bars into single HTF bar."""
        first = bars[0]
        last = bars[-1]
        
        max_h = max(b.h for b in bars)
        min_l = min(b.l for b in bars)
        sum_v = sum(b.v for b in bars)
        
        return BarV1(
            symbol=symbol,
            tf=target_tf,
            open_ts=first.open_ts,
            close_ts=last.close_ts,
            o=first.o,
            h=max_h,
            l=min_l,
            c=last.c,
            v=sum_v,
            is_closed=True
        )
