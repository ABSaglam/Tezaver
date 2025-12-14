# Matrix V2 Filter Debug Tools
"""
Tools for analyzing filter squeeze in Silver strategies.

Helps identify which filter stage is eliminating signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


@dataclass
class SilverFilterStageStats:
    """Statistics for each filter stage."""
    total_patterns: int
    stage_counts: Dict[str, int] = field(default_factory=dict)
    
    def to_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dicts for DataFrame."""
        result = []
        for name, count in self.stage_counts.items():
            pct = 100.0 * count / self.total_patterns if self.total_patterns > 0 else 0.0
            result.append({
                "Aşama": name,
                "Event Sayısı": count,
                "Oran %": f"{pct:.1f}%",
            })
        return result


@dataclass
class SilverFilterDebugInfo:
    """Debug info for tightness v2 filter window."""
    tightness: float
    ml_enabled: bool
    rsi_range: Tuple[float, float]
    volume_range: Tuple[float, float]
    atr_range: Tuple[float, float]
    rsi_gap_1d_range: Optional[Tuple[float, float]] = None
    rsi_1h_range: Optional[Tuple[float, float]] = None
    stages: List[Dict[str, Any]] = field(default_factory=list)
    dataset_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SilverDataSourceStats:
    """Statistics for a data source (pattern or full_replay)."""
    data_source: str  # "pattern" or "full_replay"
    symbol: str
    timeframe: str
    start_ts: Optional[Any]  # pd.Timestamp
    end_ts: Optional[Any]  # pd.Timestamp
    num_rows: int
    num_labeled_events: int


def compute_silver_dataset_stats_from_patterns(
    symbol: str,
    timeframe: str,
) -> Optional["SilverDatasetStats"]:  # type: ignore
    """
    Compute dataset stats from pattern parquet for tightness interpolation.
    
    Returns:
        SilverDatasetStats or None if dataset not found.
    """
    import pandas as pd
    from tezaver.matrix.strategies.silver_core import SilverDatasetStats
    
    parquet_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet")
    if not parquet_path.exists():
        return None
    
    try:
        df = pd.read_parquet(parquet_path)
    except Exception:
        return None
    
    # Map column names (parquet uses feat_ prefix)
    def get_col(names: List[str]) -> Optional[str]:
        for n in names:
            if n in df.columns:
                return n
        return None
    
    rsi_col = get_col(["feat_rsi_15m", "rsi_15m", "rsi"])
    vol_col = get_col(["feat_volume_rel_15m", "volume_rel_15m", "volume_rel"])
    atr_col = get_col(["feat_atr_pct_15m", "atr_pct_15m", "atr_pct"])
    rsi_gap_col = get_col(["feat_rsi_gap_1d", "rsi_gap_1d"])
    rsi_1h_col = get_col(["feat_rsi_1h", "rsi_1h"])
    
    if rsi_col is None or vol_col is None or atr_col is None:
        return None
    
    return SilverDatasetStats(
        rsi_15m_min=float(df[rsi_col].min()),
        rsi_15m_max=float(df[rsi_col].max()),
        volume_rel_15m_min=float(df[vol_col].min()),
        volume_rel_15m_max=float(df[vol_col].max()),
        atr_pct_15m_min=float(df[atr_col].min()),
        atr_pct_15m_max=float(df[atr_col].max()),
        rsi_gap_1d_min=float(df[rsi_gap_col].min()) if rsi_gap_col else None,
        rsi_gap_1d_max=float(df[rsi_gap_col].max()) if rsi_gap_col else None,
        rsi_1h_min=float(df[rsi_1h_col].min()) if rsi_1h_col else None,
        rsi_1h_max=float(df[rsi_1h_col].max()) if rsi_1h_col else None,
    )


def _check_range(value: Optional[float], rng: Optional[tuple]) -> bool:
    """Check if value is within range (None range = pass)."""
    if rng is None:
        return True
    if value is None:
        return False
    return rng[0] <= value <= rng[1]


def analyze_silver_filter_squeeze(
    symbol: str,
    timeframe: str,
    cfg: "SilverStrategyConfig",  # type: ignore
) -> SilverFilterStageStats:
    """
    Analyze which filter stages eliminate how many patterns.
    
    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        cfg: SilverStrategyConfig with filter settings.
        
    Returns:
        SilverFilterStageStats with stage-by-stage counts.
    """
    from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
    
    # Load pattern data
    try:
        feed = ReplayDataFeed.from_symbol_timeframe_silver_patterns(symbol, timeframe)
    except FileNotFoundError:
        return SilverFilterStageStats(total_patterns=0)
    
    # Collect all patterns
    patterns: List[Dict[str, Any]] = []
    while feed.has_next():
        bar = feed.next()
        if bar:
            patterns.append(bar)
    
    total = len(patterns)
    if total == 0:
        return SilverFilterStageStats(total_patterns=0)
    
    # Stage-by-stage filtering
    stage_counts: Dict[str, int] = {}
    
    # Stage 1: RSI
    passing = [p for p in patterns if _check_range(p.get("rsi_15m"), cfg.rsi_range)]
    stage_counts["1. RSI"] = len(passing)
    
    # Stage 2: + Volume
    passing = [p for p in passing if _check_range(p.get("volume_rel"), cfg.volume_rel_range)]
    stage_counts["2. + Volume"] = len(passing)
    
    # Stage 3: + ATR
    passing = [p for p in passing if _check_range(p.get("atr_pct"), cfg.atr_pct_range)]
    stage_counts["3. + ATR"] = len(passing)
    
    # Stage 4: + Quality Score
    if cfg.min_quality_score is not None:
        passing = [p for p in passing 
                   if (p.get("quality_score") or 0) >= cfg.min_quality_score]
    stage_counts["4. + Quality"] = len(passing)
    
    # Stage 5: + ML RSI Gap 1D
    passing = [p for p in passing if _check_range(p.get("rsi_gap_1d"), cfg.rsi_gap_1d_range)]
    stage_counts["5. + ML RSI Gap"] = len(passing)
    
    # Stage 6: + ML ATR 15m
    passing = [p for p in passing if _check_range(p.get("atr_pct_15m"), cfg.atr_pct_15m_range)]
    stage_counts["6. + ML ATR"] = len(passing)
    
    # Stage 7: + ML RSI 1H
    passing = [p for p in passing if _check_range(p.get("rsi_1h"), cfg.rsi_1h_range)]
    stage_counts["7. + ML RSI 1H"] = len(passing)
    
    return SilverFilterStageStats(
        total_patterns=total,
        stage_counts=stage_counts,
    )


def load_pattern_meta(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Load pattern metadata from rally_patterns_v1_meta.json or parquet.
    
    Returns:
        Dict with start_date, end_date, num_events, years, or None if not found.
    """
    import json
    from datetime import datetime
    
    meta_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1_meta.json")
    parquet_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet")
    
    # Try to load meta JSON
    data = {}
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    
    # Extract num_events from meta
    num_events = data.get("num_events") or data.get("count") or data.get("total_patterns") or 0
    
    # Try to get dates from meta
    start_ts = data.get("start_ts") or data.get("min_timestamp")
    end_ts = data.get("end_ts") or data.get("max_timestamp")
    
    start_date = None
    end_date = None
    years = None
    
    # If no dates in meta, try to read from parquet
    if (start_ts is None or end_ts is None) and parquet_path.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(parquet_path)
            
            # Look for event_time or timestamp column
            time_col = None
            for col in ["event_time", "timestamp", "ts", "time"]:
                if col in df.columns:
                    time_col = col
                    break
            
            if time_col and len(df) > 0:
                start_dt = pd.to_datetime(df[time_col].min())
                end_dt = pd.to_datetime(df[time_col].max())
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
                years = (end_dt - start_dt).days / 365.25
                num_events = len(df)
        except Exception:
            pass
    
    # If still no dates, try parsing from meta timestamps
    if start_date is None and start_ts and end_ts:
        try:
            if isinstance(start_ts, str):
                start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
            else:
                start_dt = datetime.fromtimestamp(start_ts / 1000)
                end_dt = datetime.fromtimestamp(end_ts / 1000)
            
            start_date = start_dt.strftime("%Y-%m-%d")
            end_date = end_dt.strftime("%Y-%m-%d")
            years = (end_dt - start_dt).days / 365.25
        except Exception:
            pass
    
    if start_date is None:
        return None
    
    return {
        "start_date": start_date or "?",
        "end_date": end_date or "?",
        "num_events": num_events or 0,
        "years": years or 0.0,
    }


# =============================================================================
# Data Source Stats for UI
# =============================================================================

def compute_silver_pattern_dataset_stats(
    symbol: str,
    timeframe: str,
) -> SilverDataSourceStats:
    """
    Compute stats for pattern dataset (rally_patterns_v1.parquet).
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        SilverDataSourceStats with pattern dataset info.
    """
    import pandas as pd
    
    parquet_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        return SilverDataSourceStats(
            data_source="pattern",
            symbol=symbol,
            timeframe=timeframe,
            start_ts=None,
            end_ts=None,
            num_rows=0,
            num_labeled_events=0,
        )
    
    try:
        df = pd.read_parquet(parquet_path)
    except Exception:
        return SilverDataSourceStats(
            data_source="pattern",
            symbol=symbol,
            timeframe=timeframe,
            start_ts=None,
            end_ts=None,
            num_rows=0,
            num_labeled_events=0,
        )
    
    # Find timestamp column
    ts_col = None
    for col in ["event_time", "ts", "timestamp"]:
        if col in df.columns:
            ts_col = col
            break
    
    start_ts = None
    end_ts = None
    if ts_col and len(df) > 0:
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        start_ts = df[ts_col].min()
        end_ts = df[ts_col].max()
    
    # Count labeled events
    num_labeled = 0
    if "label_is_silver" in df.columns:
        num_labeled = int(df["label_is_silver"].sum())
    elif "label_future_max_gain_pct" in df.columns:
        num_labeled = int(df["label_future_max_gain_pct"].notna().sum())
    else:
        num_labeled = len(df)
    
    return SilverDataSourceStats(
        data_source="pattern",
        symbol=symbol,
        timeframe=timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        num_rows=len(df),
        num_labeled_events=num_labeled,
    )


def compute_silver_full_replay_dataset_stats(
    symbol: str,
    timeframe: str,
) -> SilverDataSourceStats:
    """
    Compute stats for full replay dataset (full_replay_bars_v1.parquet).
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        SilverDataSourceStats with full replay dataset info.
    """
    import pandas as pd
    
    parquet_path = Path(f"data/replay/{symbol}/{timeframe}/full_replay_bars_v1.parquet")
    
    if not parquet_path.exists():
        return SilverDataSourceStats(
            data_source="full_replay",
            symbol=symbol,
            timeframe=timeframe,
            start_ts=None,
            end_ts=None,
            num_rows=0,
            num_labeled_events=0,
        )
    
    try:
        df = pd.read_parquet(parquet_path)
    except Exception:
        return SilverDataSourceStats(
            data_source="full_replay",
            symbol=symbol,
            timeframe=timeframe,
            start_ts=None,
            end_ts=None,
            num_rows=0,
            num_labeled_events=0,
        )
    
    # Find timestamp column
    ts_col = None
    for col in ["ts", "timestamp", "event_time"]:
        if col in df.columns:
            ts_col = col
            break
    
    start_ts = None
    end_ts = None
    if ts_col and len(df) > 0:
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        start_ts = df[ts_col].min()
        end_ts = df[ts_col].max()
    
    # Count labeled events (bars with future_max_gain_pct defined)
    num_labeled = 0
    if "future_max_gain_pct" in df.columns:
        num_labeled = int(df["future_max_gain_pct"].notna().sum())
    
    return SilverDataSourceStats(
        data_source="full_replay",
        symbol=symbol,
        timeframe=timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        num_rows=len(df),
        num_labeled_events=num_labeled,
    )


def format_data_source_stats_human(stats: SilverDataSourceStats) -> str:
    """
    Format data source stats for human-readable UI display.
    
    Args:
        stats: SilverDataSourceStats object.
        
    Returns:
        Formatted string for display.
    """
    if stats.start_ts is None or stats.end_ts is None or stats.num_rows == 0:
        return f"📚 Veri kaynağı: {stats.data_source} – veri bulunamadı"
    
    try:
        start = stats.start_ts.strftime("%Y-%m-%d")
        end = stats.end_ts.strftime("%Y-%m-%d")
    except Exception:
        start = str(stats.start_ts)[:10]
        end = str(stats.end_ts)[:10]
    
    source_label = "📊 Pattern" if stats.data_source == "pattern" else "📈 Full Replay"
    
    return (
        f"{source_label} | {start} → {end} | "
        f"Satır: {stats.num_rows:,} | Label: {stats.num_labeled_events:,}"
    )

