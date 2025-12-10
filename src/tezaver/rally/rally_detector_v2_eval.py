"""
Rally Detector v2 Evaluation Module
===================================

Tools for multi-coin calibration and evaluation of Rally Detector v2 Micro-Booster.
Generates statistics and comparison reports without affecting production scanners.

Functionality:
- Run V2 booster on historical data for any symbol
- Calculate detailed statistics (gain buckets, duration stats, etc.)
- Save evaluation results to JSON for analysis

This module is part of the LAB/RESEARCH layer.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger
from tezaver.rally.rally_detector_v2 import detect_rallies_v2_micro_booster, RallyDetectorV2Params

logger = get_logger(__name__)

# Base directory for V2 evaluation stats
V2_STATS_DIR = Path("data/rally_detector_v2_stats/15m")


def load_15m_features(symbol: str) -> Optional[pd.DataFrame]:
    """
    Load 15m feature data for a symbol using standard paths.
    
    Args:
        symbol: Coin symbol (e.g., 'BTCUSDT')
        
    Returns:
        DataFrame with features or None if not found
    """
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    path = data_dir / "features_15m.parquet"
    
    if not path.exists():
        logger.warning(f"15m features not found for {symbol} at {path}")
        return None
        
    try:
        df = pd.read_parquet(path)
        # Ensure timestamp column is datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
        # Ensure required columns exist for V2
        required = ['open', 'high', 'low', 'close', 'vol_rel']
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.warning(f"Missing required columns for {symbol}: {missing}")
            return None
            
        return df
    except Exception as e:
        logger.error(f"Error loading data for {symbol}: {e}")
        return None


def run_v2_eval_for_symbol(
    symbol: str, 
    timeframe: str = "15m",
    params: Optional[RallyDetectorV2Params] = None
) -> Dict[str, Any]:
    """
    Run V2 Micro-Booster evaluation for a single symbol.
    
    Args:
        symbol: Coin symbol
        timeframe: Timeframe (currently only '15m' supported)
        params: Optional V2 parameters (uses defaults if None)
        
    Returns:
        Dictionary containing evaluation statistics
    """
    logger.info(f"Running V2 eval for {symbol} {timeframe}")
    
    if timeframe != "15m":
        raise ValueError(f"Only '15m' timeframe is supported for V2 eval, got {timeframe}")
        
    df_15m = load_15m_features(symbol)
    if df_15m is None:
        return {
            "symbol": symbol,
            "error": "Data load failed",
            "event_count": 0
        }
    
    # Run Detector
    start_time = datetime.now()
    events_df = detect_rallies_v2_micro_booster(df_15m, params=params)
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
    
    # Calculate Statistics
    stats = {
        "symbol": symbol,
        "timeframe": timeframe,
        "eval_timestamp": datetime.now().isoformat(),
        "execution_time_ms": round(duration_ms, 2),
        "event_count": len(events_df),
        "params": str(params) if params else "defaults"
    }
    
    if not events_df.empty:
        # Date Range
        stats["date_range"] = {
            "start": events_df['event_time'].min().isoformat(),
            "end": events_df['event_time'].max().isoformat()
        }
        
        # Gain Stats
        gains = events_df['future_max_gain_pct']
        stats["gain_stats"] = {
            "min": round(float(gains.min()), 4),
            "max": round(float(gains.max()), 4),
            "mean": round(float(gains.mean()), 4),
            "median": round(float(gains.median()), 4)
        }
        
        # Gain Buckets
        stats["gain_bucket_counts"] = {
            "5_to_10": int(((gains >= 0.05) & (gains < 0.10)).sum()),
            "10_to_20": int(((gains >= 0.10) & (gains < 0.20)).sum()),
            "20_plus": int((gains >= 0.20).sum())
        }
        
        # Duration Stats (Bars)
        bars = events_df['bars_to_peak']
        stats["bars_stats"] = {
            "min": int(bars.min()),
            "max": int(bars.max()),
            "mean": round(float(bars.mean()), 2)
        }
    else:
        stats["note"] = "No events detected"
        stats["event_count"] = 0
        
    return stats


def save_v2_eval_stats(symbol: str, stats: Dict[str, Any]) -> Path:
    """
    Save evaluation statistics to JSON file.
    
    Args:
        symbol: Coin symbol
        stats: Statistics dictionary
        
    Returns:
        Path to saved file
    """
    # Ensure directory exists
    V2_STATS_DIR.mkdir(parents=True, exist_ok=True)
    
    filename = f"{symbol.upper()}_v2_stats.json"
    file_path = V2_STATS_DIR / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, default=str)
        
    logger.info(f"Saved V2 eval stats for {symbol} to {file_path}")
    return file_path


def load_v2_eval_stats(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Load pre-calculated evaluation stats for a symbol.
    """
    filename = f"{symbol.upper()}_v2_stats.json"
    file_path = V2_STATS_DIR / filename
    
    if not file_path.exists():
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading eval stats for {symbol}: {e}")
        return None
