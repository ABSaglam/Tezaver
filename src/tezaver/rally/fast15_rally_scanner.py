"""
Fast15 Rally Scanner for Tezaver Mac.

Detects rapid price movements (5%+/10%+/20%+/30%) in 15m timeframe within 1-10 bars,
capturing multi-timeframe indicator snapshots at rally trigger points.

Tezaver Philosophy:
- "Hızlı yükselişler, doğru koşullarda tekrarlanabilir. 15 dakikalık vuruşlar, anı yakalar."
- "Her rally başlangıcı bir test, çoklu zaman dilimi konteksti ise anahtar."
"""

import pandas as pd
import numpy as np
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pathlib import Path

from tezaver.core import coin_cell_paths
from tezaver.core.config import (
    FAST15_RALLY_TF,
    FAST15_LOOKAHEAD_BARS,
    FAST15_RALLY_BUCKETS,
    FAST15_MIN_GAIN,
    FAST15_EVENT_GAP,
    FAST15_MACD_SLEEP_THRESHOLD,
    FAST15_MACD_WAKE_THRESHOLD,
    FAST15_MACD_RUN_THRESHOLD,
    get_turkey_now,
)
from tezaver.snapshots.snapshot_engine import load_features
from tezaver.core.logging_utils import get_logger

# Rally Quality Engine imports
from tezaver.rally.rally_quality_engine import (
    enrich_rally_events_with_quality,
    get_default_rally_quality_config,
)
from tezaver.context.multitimeframe_context import (
    ensure_mtc_columns,
    validate_mtc_schema,
    get_required_mtc_columns,
)
from tezaver.rally.rally_narrative_engine import enrich_with_narratives

logger = get_logger(__name__)


@dataclass
class Fast15RallyScanResult:
    """Result container for Fast15 rally scan."""
    symbol: str
    num_events_total: int
    num_events_by_bucket: Dict[str, int]
    output_path: Path
    summary_path: Path


def classify_macd_phase(hist: float, signal: float, line: float, is_rising: bool = None) -> str:
    """
    Classifies MACD phase based on histogram and momentum.
    
    Returns:
        "UYKU": Very small histogram (sleeping/consolidation)
        "UYANIS": Rising from sleep (awakening)
        "KOSU": Strong positive momentum (running)
        "YORGUNLUK": Positive but declining (fatigue)
    """
    abs_hist = abs(hist)
    
    # Sleep phase - very small activity
    if abs_hist < FAST15_MACD_SLEEP_THRESHOLD:
        return "UYKU"
    
    # If hist is negative, force UYKU or special handling
    if hist < 0:
        return "UYKU"
    
    # Positive histogram cases
    if abs_hist >= FAST15_MACD_RUN_THRESHOLD:
        # Strong momentum
        if is_rising is not None and not is_rising:
            return "YORGUNLUK"  # Strong but weakening
        return "KOSU"
    
    elif abs_hist >= FAST15_MACD_WAKE_THRESHOLD:
        # Medium momentum
        if is_rising is not None and is_rising:
            return "UYANIS"  # Accelerating
        return "YORGUNLUK"  # Decelerating
    
    else:
        # Small positive momentum
        if is_rising is not None and is_rising:
            return "UYANIS"
        return "UYKU"


def determine_rally_bucket(gain_pct: float, buckets: List[float] = FAST15_RALLY_BUCKETS) -> str:
    """
    Maps gain percentage to bucket label.
    
    Args:
        gain_pct: Gain as fraction (0.10 = 10%)
        buckets: Thresholds [0.05, 0.10, 0.20, 0.30]
    
    Returns:
        "5p_10p", "10p_20p", "20p_30p", or "30p_plus"
    """
    if gain_pct < buckets[0]:
        return None  # Below minimum
        
    labels = ["5p_10p", "10p_20p", "20p_30p", "30p_plus"]
    
    # Iterate through buckets to find which range it falls into
    for i in range(len(buckets) - 1):
        if gain_pct < buckets[i+1]:
            # Falls between current bucket and next bucket
            # e.g. buckets[0] <= gain < buckets[1] -> labels[0]
            if i < len(labels):
                return labels[i]
            return f"{int(buckets[i]*100)}p_{int(buckets[i+1]*100)}p" # Fallback label
            
    # If we are here, gain_pct >= buckets[-1]
    # This corresponds to the highest label
    # e.g gain >= 0.30 -> labels[3] ('30p_plus')
    last_idx = len(buckets) - 1
    if last_idx < len(labels):
        return "30p_plus" # Special handling for standard case
    else:
        # Generic fallback
        return f"{int(buckets[-1]*100)}p_plus"



def find_last_closed_bar(df: pd.DataFrame, timestamp: pd.Timestamp) -> Optional[pd.Series]:
    """
    Finds the last closed bar at or before the given timestamp.
    Uses merge_asof logic: timestamp <= event_time.
    
    Returns:
        Last row as pd.Series, or None if no such bar exists.
    """
    if df.empty:
        return None
    
    # Ensure timestamp column is datetime
    if 'timestamp' not in df.columns:
        return None
    
    # Convert to datetime if needed
    df_ts = pd.to_datetime(df['timestamp'])
    ts = pd.to_datetime(timestamp)
    
    # Filter to bars at or before timestamp
    mask = df_ts <= ts
    filtered = df[mask]
    
    if filtered.empty:
        return None
    
    # Return last row
    return filtered.iloc[-1]


def detect_rallies_oracle_mode(
    df_15m: pd.DataFrame,
    window_radius: int = 10,  # Look 10 bars back/forward (Total 21)
    min_gain: float = FAST15_MIN_GAIN # 0.05
) -> pd.DataFrame:
    """
    Detects rallies using 'Oracle Mode' (Historical Rolling Extremas).
    REFINED VERSION: Handles cluster dips and prevents overlap.
    
    Logic:
    1. Find Local Dips: Low[t] == Min(Low[t-N : t+N])
    2. Find Local Peaks: High[t] == Max(High[t-N : t+N])
    3. Match Dip -> First Peak
    4. Calculate Gain
    5. Deduplicate: If multiple Dips point to same Peak, keep lowest Dip.
    
    Args:
        df_15m: 15m DataFrame
        window_radius: Number of bars to look back/forward (N)
        min_gain: Minimum gain to qualify as rally
        
    Returns:
        DataFrame with rally events
    """
    if df_15m.empty:
        return pd.DataFrame()
        
    df = df_15m.copy()
    
    # Ensure High/Low exist
    if 'high' not in df.columns or 'low' not in df.columns:
        logger.warning("Missing high/low columns")
        return pd.DataFrame()
        
    # Calculate Rolling Min/Max (Center=True looks forward and backward)
    window_size = (window_radius * 2) + 1
    
    # Find Local Dips (Swing Lows)
    df['rolling_min'] = df['low'].rolling(window=window_size, center=True).min()
    df['is_dip'] = (df['low'] == df['rolling_min']) & df['rolling_min'].notna()
    
    # Find Local Peaks (Swing Highs)
    df['rolling_max'] = df['high'].rolling(window=window_size, center=True).max()
    df['is_peak'] = (df['high'] == df['rolling_max']) & df['rolling_max'].notna()
    
    # Extract indices
    dip_indices = df.index[df['is_dip']].tolist()
    peak_indices = df.index[df['is_peak']].tolist()
    
    raw_events = []
    
    # Maximum lookahead for peak search (60 bars = 15 hours for 15m)
    MAX_PEAK_LOOKAHEAD = 60
    
    # First Pass: Find all potential dip-peak pairs
    for dip_idx in dip_indices:
        # Find subsequent peaks within lookahead window
        future_peaks = [p for p in peak_indices if dip_idx < p <= dip_idx + MAX_PEAK_LOOKAHEAD]
        
        if not future_peaks:
            continue
        
        dip_price = df.at[dip_idx, 'close']
        if dip_price <= 0:
            continue
        
        # Find the peak with MAXIMUM gain (not just first peak)
        best_peak_idx = None
        best_gain = 0
        
        for peak_idx in future_peaks:
            peak_price = df.at[peak_idx, 'high']
            gain_pct = (peak_price - dip_price) / dip_price
            
            if gain_pct > best_gain:
                best_gain = gain_pct
                best_peak_idx = peak_idx
        
        # Only include if best gain meets threshold
        if best_gain >= min_gain and best_peak_idx is not None:
            bars_to_peak = best_peak_idx - dip_idx
            
            raw_events.append({
                'event_index': dip_idx,
                'event_time': df.at[dip_idx, 'timestamp'],
                'future_max_gain_pct': best_gain,
                'bars_to_peak': bars_to_peak,
                'peak_index': best_peak_idx,  # Used for dedup
                'dip_price': df.at[dip_idx, 'low'] # Used for finding 'lowest' dip
            })
            
    if not raw_events:
        return pd.DataFrame()
        
    # Deduplication Logic (Ragged Bottoms Handling)
    # If multiple events share the same 'peak_index', it means a ragged bottom pointing to same rally.
    # We should keep the one with the lowest DIP PRICE (best entry).
    
    df_raw = pd.DataFrame(raw_events)
    
    # Group by peak_index and take the one with min dip_price
    # If dip prices are equal, take the first one (earliest)
    events_dedup = df_raw.sort_values('dip_price').groupby('peak_index').first().reset_index()
    
    # Sort by time
    events_dedup = events_dedup.sort_values('event_index').reset_index(drop=True)
    
    # Calculate buckets again (since they are not in groupby result if not included)
    # Actually, we didn't add bucket in raw_events, let's add it now
    events = []
    for _, row in events_dedup.iterrows():
         bucket = determine_rally_bucket(row['future_max_gain_pct'])
         if bucket:
             events.append({
                 'event_index': int(row['event_index']),
                 'event_time': row['event_time'],
                 'future_max_gain_pct': float(row['future_max_gain_pct']),
                 'bars_to_peak': int(row['bars_to_peak']),
                 'rally_bucket': bucket
             })
             
    return pd.DataFrame(events)



def enrich_event_with_multitf_snapshot(
    event_time: pd.Timestamp,
    event_index: int,
    df_15m: pd.DataFrame,
    df_1h: Optional[pd.DataFrame],
    df_4h: Optional[pd.DataFrame],
    df_1d: Optional[pd.DataFrame]
) -> dict:
    """
    Enriches a single rally event with multi-timeframe indicator snapshot.
    
    Args:
        event_time: Timestamp of the rally trigger
        event_index: Index in df_15m
        df_15m: 15m features DataFrame
        df_1h: 1h features DataFrame (optional)
        df_4h: 4h features DataFrame (optional)
        df_1d: 1d features DataFrame (optional)
    
    Returns:
        Dictionary with indicator values from all timeframes
    """
    snapshot = {}
    
    # 15m snapshot (direct index)
    if event_index < len(df_15m):
        row_15m = df_15m.iloc[event_index]
        
        snapshot['rsi_15m'] = row_15m.get('rsi', np.nan)
        snapshot['rsi_ema_15m'] = row_15m.get('rsi_ema', np.nan)
        snapshot['volume_rel_15m'] = row_15m.get('vol_rel', np.nan)  # Fixed: vol_rel not volume_rel
        
        # MACD
        snapshot['macd_line_15m'] = row_15m.get('macd_line', np.nan)
        snapshot['macd_signal_15m'] = row_15m.get('macd_signal', np.nan)
        snapshot['macd_hist_15m'] = row_15m.get('macd_hist', np.nan)
        
        # Classify MACD phase
        macd_hist = snapshot['macd_hist_15m']
        if not pd.isna(macd_hist):
            # Simple version - could check if rising by comparing with previous bar
            snapshot['macd_phase_15m'] = classify_macd_phase(
                macd_hist,
                snapshot['macd_signal_15m'],
                snapshot['macd_line_15m']
            )
        else:
            snapshot['macd_phase_15m'] = "UNKNOWN"
        
        # ATR as percentage (atr / close * 100)
        atr = row_15m.get('atr', np.nan)
        close = row_15m.get('close', np.nan)
        if not pd.isna(atr) and not pd.isna(close) and close > 0:
            snapshot['atr_pct_15m'] = (atr / close) * 100
        else:
            snapshot['atr_pct_15m'] = np.nan
    
    # 1h snapshot (merge_asof logic)
    if df_1h is not None and not df_1h.empty:
        row_1h = find_last_closed_bar(df_1h, event_time)
        if row_1h is not None:
            snapshot['rsi_1h'] = row_1h.get('rsi', np.nan)
            snapshot['rsi_ema_1h'] = row_1h.get('rsi_ema', np.nan)
            snapshot['macd_hist_1h'] = row_1h.get('macd_hist', np.nan)
            snapshot['macd_phase_1h'] = classify_macd_phase(
                row_1h.get('macd_hist', 0),
                row_1h.get('macd_signal', 0),
                row_1h.get('macd_line', 0)
            ) if not pd.isna(row_1h.get('macd_hist')) else "UNKNOWN"
            snapshot['trend_soul_1h'] = row_1h.get('trend_soul_score', np.nan)
            snapshot['regime_1h'] = row_1h.get('regime', "unknown")
            snapshot['volume_rel_1h'] = row_1h.get('vol_rel', np.nan)  # Fixed: vol_rel not volume_rel
        else:
            # Fill with NaN
            for key in ['rsi_1h', 'rsi_ema_1h', 'macd_hist_1h', 'trend_soul_1h', 'volume_rel_1h']:
                snapshot[key] = np.nan
            snapshot['macd_phase_1h'] = "UNKNOWN"
            snapshot['regime_1h'] = "unknown"
    else:
        for key in ['rsi_1h', 'rsi_ema_1h', 'macd_hist_1h', 'trend_soul_1h', 'volume_rel_1h']:
            snapshot[key] = np.nan
        snapshot['macd_phase_1h'] = "UNKNOWN"
        snapshot['regime_1h'] = "unknown"
    
    # 4h snapshot
    if df_4h is not None and not df_4h.empty:
        row_4h = find_last_closed_bar(df_4h, event_time)
        if row_4h is not None:
            snapshot['rsi_4h'] = row_4h.get('rsi', np.nan)
            snapshot['rsi_ema_4h'] = row_4h.get('rsi_ema', np.nan)
            snapshot['macd_hist_4h'] = row_4h.get('macd_hist', np.nan)
            snapshot['macd_phase_4h'] = classify_macd_phase(
                row_4h.get('macd_hist', 0),
                row_4h.get('macd_signal', 0),
                row_4h.get('macd_line', 0)
            ) if not pd.isna(row_4h.get('macd_hist')) else "UNKNOWN"
            snapshot['trend_soul_4h'] = row_4h.get('trend_soul_score', np.nan)
            snapshot['regime_4h'] = row_4h.get('regime', "unknown")
            snapshot['volume_rel_4h'] = row_4h.get('vol_rel', np.nan)  # Fixed: vol_rel not volume_rel
        else:
            for key in ['rsi_4h', 'rsi_ema_4h', 'macd_hist_4h', 'trend_soul_4h', 'volume_rel_4h']:
                snapshot[key] = np.nan
            snapshot['macd_phase_4h'] = "UNKNOWN"
            snapshot['regime_4h'] = "unknown"
    else:
        for key in ['rsi_4h', 'rsi_ema_4h', 'macd_hist_4h', 'trend_soul_4h', 'volume_rel_4h']:
            snapshot[key] = np.nan
        snapshot['macd_phase_4h'] = "UNKNOWN"
        snapshot['regime_4h'] = "unknown"
    
    # 1d snapshot
    if df_1d is not None and not df_1d.empty:
        row_1d = find_last_closed_bar(df_1d, event_time)
        if row_1d is not None:
            snapshot['rsi_1d'] = row_1d.get('rsi', np.nan)
            snapshot['rsi_ema_1d'] = row_1d.get('rsi_ema', np.nan)
            snapshot['macd_hist_1d'] = row_1d.get('macd_hist', np.nan)
            snapshot['macd_phase_1d'] = classify_macd_phase(
                row_1d.get('macd_hist', 0),
                row_1d.get('macd_signal', 0),
                row_1d.get('macd_line', 0)
            ) if not pd.isna(row_1d.get('macd_hist')) else "UNKNOWN"
            snapshot['trend_soul_1d'] = row_1d.get('trend_soul_score', np.nan)
            snapshot['regime_1d'] = row_1d.get('regime', "unknown")
            snapshot['volume_rel_1d'] = row_1d.get('vol_rel', np.nan)  # Fixed: vol_rel not volume_rel
        else:
            for key in ['rsi_1d', 'rsi_ema_1d', 'macd_hist_1d', 'trend_soul_1d', 'volume_rel_1d']:
                snapshot[key] = np.nan
            snapshot['macd_phase_1d'] = "UNKNOWN"
            snapshot['regime_1d'] = "unknown"
    else:
        for key in ['rsi_1d', 'rsi_ema_1d', 'macd_hist_1d', 'trend_soul_1d', 'volume_rel_1d']:
            snapshot[key] = np.nan
        snapshot['macd_phase_1d'] = "UNKNOWN"
        snapshot['regime_1d'] = "unknown"
    
    return snapshot


def generate_summary_stats(events_df: pd.DataFrame, symbol: str) -> dict:
    """
    Generates bucket-level statistics from events DataFrame.
    
    Returns:
        Dictionary with structure matching fast15_rallies_summary.json spec
    """
    if events_df.empty:
        return {
            "symbol": symbol,
            "generated_at": get_turkey_now().isoformat(),
            "meta": {
                "total_events": 0,
                "lookahead_bars": FAST15_LOOKAHEAD_BARS,
                "min_gain": FAST15_MIN_GAIN
            },
            "buckets": {},
            "summary_tr": f"{symbol} için 15m taramasında hiçbir rally bulunamadı."
        }
    
    summary = {
        "symbol": symbol,
        "generated_at": get_turkey_now().isoformat(),
        "meta": {
            "total_events": len(events_df),
            "lookahead_bars": FAST15_LOOKAHEAD_BARS,
            "min_gain": FAST15_MIN_GAIN
        },
        "buckets": {}
    }
    
    # Process each bucket
    for bucket_name in ["5p_10p", "10p_20p", "20p_30p", "30p_plus"]:
        df_bucket = events_df[events_df['rally_bucket'] == bucket_name]
        
        if df_bucket.empty:
            continue
        
        bucket_stats = {
            "event_count": len(df_bucket),
            "avg_future_max_gain_pct": float(df_bucket['future_max_gain_pct'].mean()),
            "median_future_max_gain_pct": float(df_bucket['future_max_gain_pct'].median()),
            "avg_bars_to_peak": float(df_bucket['bars_to_peak'].mean()),
        }
        
        # RSI 15m stats
        if 'rsi_15m' in df_bucket.columns:
            rsi_data = df_bucket['rsi_15m'].dropna()
            if len(rsi_data) > 0:
                bucket_stats['rsi_15m'] = {
                    "mean": float(rsi_data.mean()),
                    "p90": float(rsi_data.quantile(0.9)),
                    "gt_70_ratio": float((rsi_data > 70).sum() / len(rsi_data))
                }
        
        # RSI EMA 15m stats
        if 'rsi_ema_15m' in df_bucket.columns:
            rsi_ema_data = df_bucket['rsi_ema_15m'].dropna()
            if len(rsi_ema_data) > 0:
                bucket_stats['rsi_ema_15m'] = {
                    "mean": float(rsi_ema_data.mean()),
                    "gt_60_ratio": float((rsi_ema_data > 60).sum() / len(rsi_ema_data))
                }
        
        # Volume rel 15m stats
        if 'volume_rel_15m' in df_bucket.columns:
            vol_data = df_bucket['volume_rel_15m'].dropna()
            if len(vol_data) > 0:
                bucket_stats['volume_rel_15m'] = {
                    "mean": float(vol_data.mean()),
                    "gt_1_5_ratio": float((vol_data > 1.5).sum() / len(vol_data))
                }
        
        # MACD phase distribution (15m)
        if 'macd_phase_15m' in df_bucket.columns:
            phase_counts = df_bucket['macd_phase_15m'].value_counts()
            total = len(df_bucket)
            bucket_stats['macd_phase_15m'] = {
                phase: float(count / total) 
                for phase, count in phase_counts.items()
            }
        
        # Trend soul 1h stats
        if 'trend_soul_1h' in df_bucket.columns:
            trend_data = df_bucket['trend_soul_1h'].dropna()
            if len(trend_data) > 0:
                bucket_stats['trend_soul_1h'] = {
                    "mean": float(trend_data.mean()),
                    "gt_60_ratio": float((trend_data > 60).sum() / len(trend_data))
                }
        
        # Trend soul 4h stats
        if 'trend_soul_4h' in df_bucket.columns:
            trend_data = df_bucket['trend_soul_4h'].dropna()
            if len(trend_data) > 0:
                bucket_stats['trend_soul_4h'] = {
                    "mean": float(trend_data.mean()),
                    "gt_60_ratio": float((trend_data > 60).sum() / len(trend_data))
                }
        
        # Regime 1d distribution
        if 'regime_1d' in df_bucket.columns:
            regime_counts = df_bucket['regime_1d'].value_counts()
            bucket_stats['regime_1d_counts'] = regime_counts.to_dict()
        
        summary['buckets'][bucket_name] = bucket_stats
    
    return summary


def generate_turkish_summary(stats: dict) -> str:
    """
    Generates human-readable Turkish summary from stats.
    
    Args:
        stats: Dictionary from generate_summary_stats
    
    Returns:
        Turkish narrative string
    """
    symbol = stats['symbol']
    total = stats['meta']['total_events']
    
    if total == 0:
        return f"{symbol} için 15m taramasında hiçbir rally bulunamadı."
    
    lines = [f"{symbol} coin'inde 15 dakikalık grafikte {total} adet hızlı yükseliş tespit edildi.\n"]
    
    # Process each bucket with >= 20 samples
    for bucket_name, threshold_label in [
        ("20p_30p", "%20-30"),
        ("10p_20p", "%10-20"),
        ("5p_10p", "%5-10"),
        ("30p_plus", "%30+")
    ]:
        if bucket_name not in stats['buckets']:
            continue
        
        bucket = stats['buckets'][bucket_name]
        count = bucket['event_count']
        
        if count < 20:
            continue  # Skip small samples
        
        components = []
        
        # RSI conditions
        if 'rsi_15m' in bucket:
            rsi_ratio = bucket['rsi_15m'].get('gt_70_ratio', 0)
            if rsi_ratio >= 0.7:
                components.append(f"%{int(rsi_ratio * 100)}'inde 15m RSI 70'in üzerinde")
        
        # RSI EMA conditions
        if 'rsi_ema_15m' in bucket:
            rsi_ema_ratio = bucket['rsi_ema_15m'].get('gt_60_ratio', 0)
            if rsi_ema_ratio >= 0.6:
                components.append(f"%{int(rsi_ema_ratio * 100)}'inde 15m RSI-EMA 60'ın üstünde")
        
        # MACD phase
        if 'macd_phase_15m' in bucket:
            phases = bucket['macd_phase_15m']
            active_ratio = phases.get('UYANIS', 0) + phases.get('KOSU', 0)
            if active_ratio >= 0.7:
                components.append(f"%{int(active_ratio * 100)}'inde MACD fazı UYANIS veya KOSU")
        
        # Trend soul 1h
        if 'trend_soul_1h' in bucket:
            trend_ratio = bucket['trend_soul_1h'].get('gt_60_ratio', 0)
            if trend_ratio >= 0.6:
                components.append(f"%{int(trend_ratio * 100)}'inde 1h TrendSoul 60'ın üzerinde")
        
        if components:
            conditions_text = ", ".join(components)
            lines.append(
                f"• {threshold_label} yükseliş: {count} örnek. "
                f"Bunların {conditions_text}."
            )
    
    if len(lines) == 1:
        lines.append("Detaylı koşul bilgisi için veri analizi gerekiyor.")
    
    return "\n".join(lines)


def run_fast15_scan_for_symbol(symbol: str) -> Fast15RallyScanResult:
    """
    Main entry point: Runs Fast15 rally scan for a single symbol.
    
    Args:
        symbol: Coin symbol (e.g., "BTCUSDT")
    
    Returns:
        Fast15RallyScanResult with paths and event counts
    
    Raises:
        FileNotFoundError: If 15m features don't exist
        ValueError: If data is invalid
    """
    logger.info(f"=== Starting Fast15 Rally Scan for {symbol} ===")
    
    # Load 15m features
    try:
        df_15m = load_features(symbol, FAST15_RALLY_TF)
    except FileNotFoundError:
        logger.warning(f"15m features not found for {symbol}, skipping")
        raise
    
    if df_15m.empty:
        logger.warning(f"15m features empty for {symbol}")
        raise ValueError(f"Empty 15m features for {symbol}")
    
    # Ensure timestamp column is datetime
    if 'timestamp' not in df_15m.columns:
        if 'open_time' in df_15m.columns:
            df_15m['timestamp'] = pd.to_datetime(df_15m['open_time'], unit='ms')
        else:
            df_15m['timestamp'] = pd.to_datetime(df_15m.index)
    else:
        # Convert timestamp to datetime if it's int64 (milliseconds)
        if df_15m['timestamp'].dtype == 'int64':
            df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        else:
            df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'])
    
    # Load multi-TF features (optional)
    df_1h = None
    df_4h = None
    df_1d = None
    
    try:
        df_1h = load_features(symbol, "1h")
        if 'timestamp' not in df_1h.columns:
            if 'open_time' in df_1h.columns:
                df_1h['timestamp'] = pd.to_datetime(df_1h['open_time'], unit='ms')
            else:
                df_1h['timestamp'] = pd.to_datetime(df_1h.index)
        else:
            if df_1h['timestamp'].dtype == 'int64':
                df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    except FileNotFoundError:
        logger.warning(f"1h features not found for {symbol}, will use NaN")
    
    try:
        df_4h = load_features(symbol, "4h")
        if 'timestamp' not in df_4h.columns:
            if 'open_time' in df_4h.columns:
                df_4h['timestamp'] = pd.to_datetime(df_4h['open_time'], unit='ms')
            else:
                df_4h['timestamp'] = pd.to_datetime(df_4h.index)
        else:
            if df_4h['timestamp'].dtype == 'int64':
                df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    except FileNotFoundError:
        logger.warning(f"4h features not found for {symbol}, will use NaN")
    
    try:
        df_1d = load_features(symbol, "1d")
        if 'timestamp' not in df_1d.columns:
            if 'open_time' in df_1d.columns:
                df_1d['timestamp'] = pd.to_datetime(df_1d['open_time'], unit='ms')
            else:
                df_1d['timestamp'] = pd.to_datetime(df_1d.index)
        else:
            if df_1d['timestamp'].dtype == 'int64':
                df_1d['timestamp'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    except FileNotFoundError:
        logger.warning(f"1d features not found for {symbol}, will use NaN")
    
    # Detect rally events ORACLE MODE
    events_df = detect_rallies_oracle_mode(
        df_15m,
        window_radius=10, # 10 bars back, 10 bars forward
        min_gain=FAST15_MIN_GAIN 
    )
    
    if events_df.empty:
        # Still save empty result
        output_path = coin_cell_paths.get_fast15_rallies_path(symbol)
        summary_path = coin_cell_paths.get_fast15_rallies_summary_path(symbol)
        
        # Save empty parquet
        pd.DataFrame().to_parquet(output_path, index=False)
        
        # Save summary
        stats = generate_summary_stats(events_df, symbol)
        stats['summary_tr'] = f"{symbol} için 15m taramasında hiçbir rally bulunamadı."
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"No events found for {symbol}, saved empty results")
        
        return Fast15RallyScanResult(
            symbol=symbol,
            num_events_total=0,
            num_events_by_bucket={},
            output_path=output_path,
            summary_path=summary_path
        )
    
    # Enrich events with multi-TF snapshots
    enriched_records = []
    
    for _, event in events_df.iterrows():
        # Convert event_time to pd.Timestamp if it's not already
        event_time = pd.to_datetime(event['event_time'])
        
        snapshot = enrich_event_with_multitf_snapshot(
            event_time,
            event['event_index'],
            df_15m,
            df_1h,
            df_4h,
            df_1d
        )
        
        # Combine event info with snapshot
        record = {
            'symbol': symbol,
            'event_time': event_time,  # Use converted datetime
            'rally_bucket': event['rally_bucket'],
            'future_max_gain_pct': event['future_max_gain_pct'],
            'bars_to_peak': event['bars_to_peak'],
            **snapshot
        }
        
        enriched_records.append(record)
    
    # Create final DataFrame from enriched events
    df_final = pd.DataFrame(enriched_records)
    df_final = df_final.sort_values('event_time').reset_index(drop=True)
    
    # ========================================================================
    # RALLY QUALITY ENRICHMENT (Rally v2)
    # ========================================================================
    logger.info(f"Enriching with Rally v2 quality metrics for {symbol}...")
    
    try:
        # Create close prices Series with datetime index for quality enrichment
        close_prices = df_15m.set_index('timestamp')['close'].copy()
        
        # Enrich with quality metrics
        df_final = enrich_rally_events_with_quality(
            events_df=df_final,
            prices=close_prices,
            timeframe="15m",
            cfg_map=None  # Use defaults
        )
        
        logger.info(f"Successfully added quality metrics (shape, score, retention, etc.)")
    except Exception as e:
        logger.warning(f"Failed to enrich with quality metrics: {e}", exc_info=True)
        # Add empty columns if enrichment fails
        df_final["rally_shape"] = "unknown"
        df_final["quality_score"] = 0.0
        df_final["pre_peak_drawdown_pct"] = 0.0
        df_final["trend_efficiency"] = 0.0
        df_final["retention_10_pct"] = 0.0
    
    # ========================================================================
    # NARRATIVE ENGINE (Scenario Analysis)
    # ========================================================================
    logger.info(f"Running Rally Narrative Engine for {symbol}...")
    try:
        df_final = enrich_with_narratives(df_final)
        logger.info(f"Narratives generated: {df_final['scenario_id'].value_counts().to_dict()}")
    except Exception as e:
        logger.error(f"Narrative engine failed: {e}", exc_info=True)
        # Add fallback empty columns to prevent failure
        df_final['scenario_id'] = "SCENARIO_NEUTRAL"
        df_final['scenario_label'] = "Belirsiz"
        df_final['narrative_tr'] = "Analiz hatası."

    # ========================================================================
    # MTC SCHEMA ENFORCEMENT
    # ========================================================================
    try:
        # 1. Add event timeframe metadata
        df_final["event_tf"] = "15m"
        
        # 2. Enforce MTC schema
        # Current version requires 15m, 1h, 4h, 1d (1w is optional for now)
        required_tfs = ["15m", "1h", "4h", "1d"]
        
        # Ensure columns exist (adds missing ones as NaN)
        df_final = ensure_mtc_columns(df_final, required_tfs)
        
        # Validate (optional in prod, but good for Dev)
        validate_mtc_schema(df_final, required_tfs)
        
        logger.info(f"MTC Schema enforced for {len(df_final)} events across {required_tfs}")
        
    except Exception as e:
        logger.error(f"Failed to enforce MTC schema: {e}", exc_info=True)
        # We don't stop execution, but data might be non-compliant
    
    # ========================================================================
    
    # Save parquet
    output_path = coin_cell_paths.get_fast15_rallies_path(symbol)
    df_final.to_parquet(output_path, index=False)
    logger.info(f"Saved {len(df_final)} events to {output_path}")
    
    # Generate and save summary
    stats = generate_summary_stats(df_final, symbol)
    stats['summary_tr'] = generate_turkish_summary(stats)
    
    summary_path = coin_cell_paths.get_fast15_rallies_summary_path(symbol)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved summary to {summary_path}")
    
    # Count by bucket
    bucket_counts = df_final['rally_bucket'].value_counts().to_dict()
    
    logger.info(f"=== Fast15 Scan Complete for {symbol} ===")
    logger.info(f"Total events: {len(df_final)}")
    logger.info(f"By bucket: {bucket_counts}")
    
    return Fast15RallyScanResult(
        symbol=symbol,
        num_events_total=len(df_final),
        num_events_by_bucket=bucket_counts,
        output_path=output_path,
        summary_path=summary_path
    )
