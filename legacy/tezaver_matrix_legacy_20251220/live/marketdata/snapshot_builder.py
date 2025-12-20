# Snapshot Builder
"""
Build market snapshots from bar data.

Snapshot is what gets passed to UnifiedEngine.tick().
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd


def build_snapshot_from_bars(
    bars: pd.DataFrame,
    symbol: str = "",
    timeframe: str = "",
) -> Dict[str, Any]:
    """
    Build market snapshot from bars.
    
    Args:
        bars: DataFrame with OHLCV data
        symbol: Symbol name
        timeframe: Timeframe string
        
    Returns:
        Snapshot dict for tick()
    """
    if bars is None or bars.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "ts": datetime.utcnow().isoformat(),
            "close": None,
            "volume": None,
            "bar_count": 0,
            "error": "no_bars",
        }
    
    latest = bars.iloc[-1]
    
    # Extract bar timestamps
    bar_ts = latest.get("ts")
    bar_ts_iso = bar_ts.isoformat() if hasattr(bar_ts, "isoformat") else str(bar_ts) if bar_ts else None
    
    # Calculate bar_close_ts from close_time_ms or open_time + interval
    bar_close_ts = None
    bar_close_ts_iso = None
    is_closed = False
    
    if "close_time_ms" in latest.index and pd.notna(latest.get("close_time_ms")):
        # Use close_time_ms from Binance kline
        bar_close_ts = datetime.utcfromtimestamp(latest.get("close_time_ms") / 1000)
        bar_close_ts_iso = bar_close_ts.isoformat()
    elif "open_time_ms" in latest.index and pd.notna(latest.get("open_time_ms")):
        # Calculate from open_time + timeframe
        tf_ms = 15 * 60 * 1000  # default 15m
        if timeframe.endswith("m"):
            tf_ms = int(timeframe[:-1]) * 60 * 1000
        elif timeframe.endswith("h"):
            tf_ms = int(timeframe[:-1]) * 60 * 60 * 1000
        
        open_time_ms = latest.get("open_time_ms")
        close_time_ms = open_time_ms + tf_ms - 1
        bar_close_ts = datetime.utcfromtimestamp(close_time_ms / 1000)
        bar_close_ts_iso = bar_close_ts.isoformat()
    
    # Check is_closed flag if available
    if "is_closed" in latest.index:
        is_closed = bool(latest.get("is_closed"))
    
    # Basic snapshot
    snapshot = {
        "symbol": symbol,
        "timeframe": timeframe,
        "ts": bar_ts_iso or datetime.utcnow().isoformat(),
        "bar_ts": bar_ts_iso,
        "bar_close_ts": bar_close_ts_iso,
        "is_closed": is_closed,
        "close": float(latest.get("close", 0)),
        "open": float(latest.get("open", 0)),
        "high": float(latest.get("high", 0)),
        "low": float(latest.get("low", 0)),
        "volume": float(latest.get("volume", 0)),
        "bar_count": len(bars),
    }
    
    # Add placeholders for expected features (can be computed later)
    snapshot["rsi_15m"] = None
    snapshot["volume_rel_15m"] = None
    snapshot["atr_pct_15m"] = None
    snapshot["quality_score"] = None
    
    # Compute simple features if enough bars
    if len(bars) >= 14:
        # Simple RSI approximation
        closes = bars["close"].astype(float)
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        snapshot["rsi_15m"] = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None
    
    if len(bars) >= 20:
        # Volume relative to 20-bar average
        vols = bars["volume"].astype(float)
        vol_avg = vols.rolling(20).mean().iloc[-1]
        snapshot["volume_rel_15m"] = float(vols.iloc[-1] / vol_avg) if vol_avg > 0 else None
    
    if len(bars) >= 14:
        # ATR percentage
        highs = bars["high"].astype(float)
        lows = bars["low"].astype(float)
        closes = bars["close"].astype(float)
        
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        snapshot["atr_pct_15m"] = float(atr / closes.iloc[-1] * 100) if closes.iloc[-1] > 0 else None
    
    return snapshot


def compute_snapshot_fingerprint(snapshot: Dict[str, Any]) -> str:
    """Create fingerprint for snapshot deduplication."""
    import hashlib
    key_fields = ["symbol", "timeframe", "ts", "close"]
    parts = [str(snapshot.get(k, "")) for k in key_fields]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]
