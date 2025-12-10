"""
Tezaver Rally Pattern Encoder v1
================================

Builds ML/AI-ready feature datasets from BTC 15m rally events.
Each row = 1 rally event with pre-rally window features and labels.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json

import numpy as np
import pandas as pd


@dataclass
class PatternWindowConfig:
    """
    Configuration for rally pattern extraction.
    """
    lookback_bars: int = 12  # bars before rally start (~3 hours for 15m)
    min_required_bars: int = 8  # minimum bars required
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"


def _load_btc_15m_rally_dataset() -> pd.DataFrame:
    """Load BTC 15m rally dataset."""
    rallies_path = Path("library/fast15_rallies/BTCUSDT/fast15_rallies.parquet")
    if not rallies_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(rallies_path)


def _compute_slope(series: pd.Series) -> float:
    """
    Simple slope: (last - first) / (n_bars - 1).
    Returns 0 if empty or single value.
    """
    s = series.dropna()
    n = len(s)
    if n <= 1:
        return 0.0
    return float((s.iloc[-1] - s.iloc[0]) / (n - 1))


def _extract_window_features_15m(window: pd.DataFrame) -> Dict[str, float]:
    """
    Extract ML features from 15m window.
    Expected columns: rsi_15m, rsi_ema_15m, volume_rel_15m, atr_pct_15m, 
                      macd_line_15m, macd_signal_15m, macd_hist_15m
    """
    feats: Dict[str, float] = {}

    def stats_prefixed(col: str, prefix: str) -> None:
        if col not in window.columns:
            return
        s = window[col].dropna()
        if s.empty:
            feats[f"{prefix}_last"] = np.nan
            feats[f"{prefix}_mean"] = np.nan
            feats[f"{prefix}_min"] = np.nan
            feats[f"{prefix}_max"] = np.nan
            feats[f"{prefix}_p25"] = np.nan
            feats[f"{prefix}_p75"] = np.nan
            feats[f"{prefix}_slope"] = 0.0
            return
        feats[f"{prefix}_last"] = float(s.iloc[-1])
        feats[f"{prefix}_mean"] = float(s.mean())
        feats[f"{prefix}_min"] = float(s.min())
        feats[f"{prefix}_max"] = float(s.max())
        feats[f"{prefix}_p25"] = float(s.quantile(0.25))
        feats[f"{prefix}_p75"] = float(s.quantile(0.75))
        feats[f"{prefix}_slope"] = _compute_slope(s)

    # RSI
    stats_prefixed("rsi_15m", "rsi15")
    stats_prefixed("rsi_ema_15m", "rsiema15")

    # RSI gap
    if "rsi_15m" in window.columns and "rsi_ema_15m" in window.columns:
        gap = window["rsi_15m"] - window["rsi_ema_15m"]
        s = gap.dropna()
        if not s.empty:
            feats["rsi_gap15_last"] = float(s.iloc[-1])
            feats["rsi_gap15_mean"] = float(s.mean())
            feats["rsi_gap15_slope"] = _compute_slope(s)

    # Volume
    stats_prefixed("volume_rel_15m", "volrel15")

    # ATR
    stats_prefixed("atr_pct_15m", "atrpct15")

    # MACD
    stats_prefixed("macd_line_15m", "macd15")
    stats_prefixed("macd_signal_15m", "macdsig15")
    stats_prefixed("macd_hist_15m", "macdhist15")

    return feats


def _extract_mtf_snapshot_features(row: pd.Series) -> Dict[str, float]:
    """
    Extract 1h / 4h / 1d snapshot features from rally event row.
    """
    feats: Dict[str, float] = {}

    for tf in ["1h", "4h", "1d"]:
        rsi_col = f"rsi_{tf}"
        rsi_ema_col = f"rsi_ema_{tf}"
        trend_col = f"trend_soul_{tf}"

        if rsi_col in row.index and pd.notna(row[rsi_col]):
            feats[f"rsi_{tf}"] = float(row[rsi_col])
        if rsi_ema_col in row.index and pd.notna(row[rsi_ema_col]):
            feats[f"rsi_ema_{tf}"] = float(row[rsi_ema_col])
            if rsi_col in row.index and pd.notna(row[rsi_col]):
                feats[f"rsi_gap_{tf}"] = float(row[rsi_col] - row[rsi_ema_col])
        if trend_col in row.index and pd.notna(row[trend_col]):
            feats[f"trend_soul_{tf}"] = float(row[trend_col])

    return feats


def _extract_event_core_features(row: pd.Series) -> Dict[str, float]:
    """
    Extract core features directly from event row (no window needed).
    """
    feats: Dict[str, float] = {}
    
    core_cols = [
        "rsi_15m", "rsi_ema_15m", "volume_rel_15m", "atr_pct_15m",
        "quality_score", "bars_to_peak", "pre_peak_drawdown_pct", "trend_efficiency"
    ]
    
    for col in core_cols:
        if col in row.index and pd.notna(row[col]):
            feats[col] = float(row[col])
    
    # RSI gap
    if "rsi_15m" in row.index and "rsi_ema_15m" in row.index:
        if pd.notna(row["rsi_15m"]) and pd.notna(row["rsi_ema_15m"]):
            feats["rsi_gap_15m"] = float(row["rsi_15m"] - row["rsi_ema_15m"])
    
    return feats


def _define_labels(row: pd.Series) -> Dict[str, Any]:
    """
    Define ML labels from rally event.
    """
    labels: Dict[str, Any] = {}

    gain = row.get("future_max_gain_pct")
    dd = row.get("pre_peak_drawdown_pct")
    
    gain_val = float(gain) if pd.notna(gain) else np.nan
    dd_val = float(dd) if pd.notna(dd) else np.nan

    labels["future_max_gain_pct"] = gain_val
    
    # Grade labels
    labels["is_diamond"] = pd.notna(gain_val) and gain_val >= 0.30
    labels["is_gold"] = pd.notna(gain_val) and 0.20 <= gain_val < 0.30
    labels["is_silver"] = pd.notna(gain_val) and 0.10 <= gain_val < 0.20
    labels["is_bronze"] = pd.notna(gain_val) and 0.05 <= gain_val < 0.10

    # Good entry: sufficient gain + acceptable pre-peak drawdown
    labels["is_good_entry_v1"] = (
        pd.notna(gain_val) and pd.notna(dd_val) and 
        gain_val >= 0.10 and dd_val >= -0.03
    )
    
    # Minimum viable: at least 5% gain
    labels["is_viable_entry"] = pd.notna(gain_val) and gain_val >= 0.05

    return labels


def build_btc_15m_rally_pattern_dataset_v1(
    cfg: Optional[PatternWindowConfig] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Build ML/AI pattern dataset from BTC 15m rally events.

    Each row = 1 rally event.
    Columns:
      - Identity: symbol, event_time, rally_bucket, rally_shape, quality_score
      - feat_*: 15m core features + 1h/4h/1d snapshot features
      - label_*: is_silver, is_good_entry_v1, future_max_gain_pct

    Returns:
      - patterns_df: DataFrame with all features and labels
      - meta: Metadata dict
    """
    if cfg is None:
        cfg = PatternWindowConfig()

    # Load rally dataset
    df = _load_btc_15m_rally_dataset()
    if df is None or df.empty:
        return pd.DataFrame(), {
            "symbol": cfg.symbol,
            "timeframe": cfg.timeframe,
            "num_events": 0,
            "num_rows": 0,
            "reason": "dataset_empty",
        }

    # Ensure event_time is datetime
    if "event_time" in df.columns:
        if not np.issubdtype(df["event_time"].dtype, np.datetime64):
            df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
        df = df.sort_values("event_time").reset_index(drop=True)

    rows: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        event_time = row.get("event_time")
        
        # Base identity fields
        base: Dict[str, Any] = {
            "symbol": cfg.symbol,
            "timeframe": cfg.timeframe,
            "event_idx": int(idx),
            "event_time": str(event_time) if event_time is not None else None,
            "rally_bucket": row.get("rally_bucket"),
            "rally_shape": row.get("rally_shape"),
        }

        # Core 15m features from event row
        feats_core = _extract_event_core_features(row)

        # Multi-timeframe snapshot features
        feats_mtf = _extract_mtf_snapshot_features(row)

        # Labels
        labels = _define_labels(row)

        # Combine all
        combined: Dict[str, Any] = {}
        combined.update(base)
        
        for k, v in feats_core.items():
            combined[f"feat_{k}"] = v
        for k, v in feats_mtf.items():
            combined[f"feat_{k}"] = v
        for k, v in labels.items():
            combined[f"label_{k}"] = v

        rows.append(combined)

    patterns_df = pd.DataFrame(rows)

    # Count label distributions
    label_cols = [c for c in patterns_df.columns if c.startswith("label_")]
    label_stats = {}
    for col in label_cols:
        if patterns_df[col].dtype == bool:
            label_stats[col] = int(patterns_df[col].sum())

    meta: Dict[str, Any] = {
        "symbol": cfg.symbol,
        "timeframe": cfg.timeframe,
        "num_events": int(df.shape[0]),
        "num_rows": int(patterns_df.shape[0]),
        "num_features": len([c for c in patterns_df.columns if c.startswith("feat_")]),
        "num_labels": len(label_cols),
        "label_counts": label_stats,
        "config": asdict(cfg),
    }

    return patterns_df, meta


def save_btc_15m_rally_pattern_dataset_v1(
    cfg: Optional[PatternWindowConfig] = None,
) -> Dict[str, Any]:
    """
    Save dataset to disk and return metadata.
    
    Output files:
      - data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet
      - data/ai_datasets/BTCUSDT/15m/rally_patterns_v1_meta.json
    """
    if cfg is None:
        cfg = PatternWindowConfig()

    patterns_df, meta = build_btc_15m_rally_pattern_dataset_v1(cfg)

    if patterns_df.empty:
        return meta

    base_dir = Path("data/ai_datasets") / cfg.symbol / cfg.timeframe
    base_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = base_dir / "rally_patterns_v1.parquet"
    meta_path = base_dir / "rally_patterns_v1_meta.json"

    patterns_df.to_parquet(parquet_path, index=False)

    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    meta["parquet_path"] = str(parquet_path)
    meta["meta_path"] = str(meta_path)
    
    return meta


def load_btc_15m_rally_pattern_dataset_v1() -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
    """
    Load saved pattern dataset and metadata.
    Returns (None, None) if files don't exist.
    """
    parquet_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
    meta_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1_meta.json")
    
    if not parquet_path.exists():
        return None, None
    
    df = pd.read_parquet(parquet_path)
    
    meta = None
    if meta_path.exists():
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    
    return df, meta


# =============================================================================
# GENERIC MULTI-COIN PATTERN ENCODER
# =============================================================================

def _load_rally_dataset_for_symbol(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load raw rally dataset for any symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").
        timeframe: Timeframe ("15m" for fast15_rallies).
        
    Returns:
        DataFrame with rally events.
        
    Raises:
        FileNotFoundError: If rally dataset doesn't exist.
    """
    if timeframe == "15m":
        rallies_path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    else:
        rallies_path = Path(f"library/time_labs/{timeframe}/{symbol}/rallies_{timeframe}.parquet")
    
    if not rallies_path.exists():
        raise FileNotFoundError(f"Rally dataset not found: {rallies_path}")
    
    return pd.read_parquet(rallies_path)


def build_rally_patterns_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
) -> Path:
    """
    Generic pattern encoder for any symbol.
    
    Builds ML-ready pattern dataset from raw rally events.
    Same feature set as BTC: feat_rsi_15m, feat_volume_rel_15m, etc.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").
        timeframe: Timeframe (default "15m").
        
    Returns:
        Path to the saved parquet file.
        
    Raises:
        FileNotFoundError: If raw rally dataset doesn't exist.
    """
    # Load raw rally dataset
    df = _load_rally_dataset_for_symbol(symbol, timeframe)
    
    if df is None or df.empty:
        raise ValueError(f"Empty rally dataset for {symbol} {timeframe}")
    
    # Ensure event_time is datetime
    if "event_time" in df.columns:
        if not np.issubdtype(df["event_time"].dtype, np.datetime64):
            df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
        df = df.sort_values("event_time").reset_index(drop=True)
    
    rows: List[Dict[str, Any]] = []
    
    for idx, row in df.iterrows():
        event_time = row.get("event_time")
        
        # Base identity fields
        base: Dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "event_idx": int(idx),
            "event_time": str(event_time) if event_time is not None else None,
            "rally_bucket": row.get("rally_bucket"),
            "rally_shape": row.get("rally_shape"),
        }
        
        # Core 15m features from event row
        feats_core = _extract_event_core_features(row)
        
        # Multi-timeframe snapshot features
        feats_mtf = _extract_mtf_snapshot_features(row)
        
        # Labels
        labels = _define_labels(row)
        
        # Combine all
        combined: Dict[str, Any] = {}
        combined.update(base)
        
        for k, v in feats_core.items():
            combined[f"feat_{k}"] = v
        for k, v in feats_mtf.items():
            combined[f"feat_{k}"] = v
        for k, v in labels.items():
            combined[f"label_{k}"] = v
        
        rows.append(combined)
    
    patterns_df = pd.DataFrame(rows)
    
    # Save to disk
    base_dir = Path("data/ai_datasets") / symbol / timeframe
    base_dir.mkdir(parents=True, exist_ok=True)
    
    parquet_path = base_dir / "rally_patterns_v1.parquet"
    meta_path = base_dir / "rally_patterns_v1_meta.json"
    
    patterns_df.to_parquet(parquet_path, index=False)
    
    # Count label distributions
    label_cols = [c for c in patterns_df.columns if c.startswith("label_")]
    label_stats = {}
    for col in label_cols:
        if patterns_df[col].dtype == bool:
            label_stats[col] = int(patterns_df[col].sum())
    
    meta: Dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "num_events": int(df.shape[0]),
        "num_rows": int(patterns_df.shape[0]),
        "num_features": len([c for c in patterns_df.columns if c.startswith("feat_")]),
        "num_labels": len(label_cols),
        "label_counts": label_stats,
        "parquet_path": str(parquet_path),
    }
    
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    return parquet_path


def build_silver_15m_patterns_for_all() -> None:
    """
    Build pattern datasets for BTC, ETH, SOL 15m.
    Skips symbols without raw rally data.
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    timeframe = "15m"
    
    for symbol in symbols:
        try:
            out = build_rally_patterns_for_symbol_timeframe(symbol, timeframe)
            
            # Load meta to show stats
            meta_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1_meta.json")
            if meta_path.exists():
                with meta_path.open("r") as f:
                    meta = json.load(f)
                silver_count = meta.get("label_counts", {}).get("label_is_silver", 0)
                print(f"[OK] {symbol} {timeframe}: {meta.get('num_rows', 0)} patterns, {silver_count} silver")
            else:
                print(f"[OK] {symbol} {timeframe}: saved to {out}")
        except FileNotFoundError as e:
            print(f"[SKIP] {symbol} {timeframe}: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        build_silver_15m_patterns_for_all()
    else:
        print("Building BTC 15m rally pattern dataset v1...")
        cfg = PatternWindowConfig()
        meta = save_btc_15m_rally_pattern_dataset_v1(cfg)
        print("\nDataset saved:")
        print(json.dumps(meta, indent=2))

