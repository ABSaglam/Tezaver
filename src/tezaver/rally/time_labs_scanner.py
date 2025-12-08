"""
Time-Labs v1 Scanner (1h & 4h)
==============================

Professional rally detection and analysis for 1h and 4h timeframes.
This module implements the core logic for "Time-Labs", integrating:
- Generic rally detection algorithm
- Multi-timeframe context enrichment
- Rally v2.0 Quality Engine
- MTC v1 Schema Enforcement
"""

import pandas as pd
import numpy as np
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from tezaver.core import coin_cell_paths
from tezaver.core.config import (
    TIME_LABS_LOOKAHEAD_BARS,
    TIME_LABS_RALLY_BUCKETS,
    TIME_LABS_MIN_GAIN,
    TIME_LABS_EVENT_GAP,
    TIME_LABS_TFS,
    get_turkey_now,
    to_turkey_time
)
from tezaver.snapshots.snapshot_engine import load_features
from tezaver.core.logging_utils import get_logger

# Rally Quality & Context imports
from tezaver.rally.rally_quality_engine import (
    enrich_rally_events_with_quality,
    get_default_rally_quality_config,
)
from tezaver.context.multitimeframe_context import (
    ensure_mtc_columns,
    validate_mtc_schema,
    get_required_mtc_columns,
)
# Re-use Fast15 logic helpers where appropriate
from tezaver.rally.fast15_rally_scanner import (
    find_last_closed_bar,
    determine_rally_bucket,
    classify_macd_phase,
    FAST15_MACD_SLEEP_THRESHOLD,
    FAST15_MACD_WAKE_THRESHOLD,
    FAST15_MACD_RUN_THRESHOLD
)

logger = get_logger(__name__)


@dataclass
class TimeframeRallyScanResult:
    """Result container for generic timeframe rally scan."""
    symbol: str
    timeframe: str  # "1h" or "4h"
    num_events_total: int
    num_events_by_bucket: Dict[str, int]
    output_path: Path
    summary_path: Path


def detect_rallies_for_timeframe(
    df_tf: pd.DataFrame,
    timeframe: str,
    min_gain_pct: float,
    lookahead_bars: int,
    buckets: List[float],
    event_gap: int,
) -> pd.DataFrame:
    """
    Generic rally detection algorithm.
    Scans looking for max high in the lookahead window.
    
    Args:
        df_tf: Features DataFrame (must contain 'timestamp', 'close', 'high')
        timeframe: "1h" or "4h" (for logging)
        min_gain_pct: Minimum gain to qualify as rally
        lookahead_bars: Future window size
        buckets: Thresholds for classification
        event_gap: Minimum bars between events
        
    Returns:
        DataFrame with columns: event_index, event_time, future_max_gain_pct,
                                bars_to_peak, rally_bucket
    """
    if df_tf.empty or 'close' not in df_tf.columns or 'high' not in df_tf.columns:
        logger.warning(f"{timeframe} DataFrame empty or missing columns")
        return pd.DataFrame()
    
    # Ensure sorted
    df_sorted = df_tf.sort_values('timestamp').reset_index(drop=True)
    close = df_sorted['close'].values
    high = df_sorted['high'].values
    timestamps = df_sorted['timestamp']
    
    events = []
    i = 0
    n = len(df_sorted)
    
    # Needs at least 1 bar ahead
    while i < n - 1:
        end_i = min(i + lookahead_bars, n - 1)
        
        if end_i <= i:
            break
            
        close_now = close[i]
        if close_now <= 0:
            i += 1
            continue
            
        # Check future highs
        future_highs = high[i+1 : end_i+1]
        if len(future_highs) == 0:
            i += 1
            continue
            
        future_max_high = np.max(future_highs)
        future_max_gain_pct = (future_max_high - close_now) / close_now
        
        if future_max_gain_pct >= min_gain_pct:
            # We found a registered rally candidate
            # Find closest peak
            peak_offset = np.argmax(future_highs) + 1
            bucket = determine_rally_bucket(future_max_gain_pct, buckets=buckets)
            
            if bucket:
                events.append({
                    'event_index': i,
                    'event_time': timestamps[i],
                    'future_max_gain_pct': future_max_gain_pct,
                    'bars_to_peak': peak_offset,
                    'rally_bucket': bucket
                })
                
                # Skip to avoid overlapping events
                i += max(1, event_gap)
                continue
        
        i += 1
        
    events_df = pd.DataFrame(events)
    if not events_df.empty:
        logger.info(f"Detected {len(events_df)} rally events in {timeframe} data")
    
    return events_df


def enrich_event_with_multitf_snapshot_generic(
    event_time: pd.Timestamp,
    base_tf: str,
    base_row: pd.Series,
    context_dfs: Dict[str, pd.DataFrame]
) -> Dict[str, Any]:
    """
    Generic enrichment function for MTC snapshots.
    
    Args:
        event_time: The timestamp of the event (limit for backward search)
        base_tf: The timeframe where event occurred ("1h")
        base_row: The exact row from base_tf DataFrame
        context_dfs: Dictionary {tf: dataframe} for other timeframes
        
    Returns:
        Dictionary of snapshot fields {field_tf: value}
    """
    snapshot = {}
    
    # 1. Process Base Timeframe (Exact Match)
    # We map base row fields to standard base names
    base_mapping = {
        'rsi': f'rsi_{base_tf}',
        'rsi_ema': f'rsi_ema_{base_tf}',
        'vol_rel': f'volume_rel_{base_tf}', # Note map: vol_rel -> volume_rel
        'macd_line': f'macd_line_{base_tf}',
        'macd_signal': f'macd_signal_{base_tf}',
        'macd_hist': f'macd_hist_{base_tf}',
        'atr': None, # special handling
        'trend_soul_score': f'trend_soul_{base_tf}',
        'regime': f'regime_{base_tf}',
        'risk_level': f'risk_level_{base_tf}',
    }
    
    for src, dst in base_mapping.items():
        if not dst: continue
        snapshot[dst] = base_row.get(src, np.nan)
        
    # Calculated Base Fields
    # ATR pct
    close = base_row.get('close', np.nan)
    atr = base_row.get('atr', np.nan)
    if pd.notna(close) and close > 0 and pd.notna(atr):
        snapshot[f'atr_pct_{base_tf}'] = (atr / close) * 100
    else:
        snapshot[f'atr_pct_{base_tf}'] = np.nan
        
    # MACD Phase
    hist = base_row.get('macd_hist', np.nan)
    if pd.notna(hist):
        # We assume "UYANIS/UNKNOWN" logic similar to Fast15
        # For simplicity in generic context, we reuse the classifier
        snapshot[f'macd_phase_{base_tf}'] = classify_macd_phase(
            hist, 
            base_row.get('macd_signal', 0), 
            base_row.get('macd_line', 0)
        )
    else:
        snapshot[f'macd_phase_{base_tf}'] = "UNKNOWN"

    
    # 2. Process Context Timeframes (Merge Asof)
    target_fields = ['rsi', 'rsi_ema', 'vol_rel', 'macd_line', 'macd_signal', 'macd_hist', 
                     'trend_soul_score', 'regime', 'risk_level', 'atr', 'close']
    
    for tf, df_ctx in context_dfs.items():
        if tf == base_tf: 
            continue # already handled
            
        row = find_last_closed_bar(df_ctx, event_time)
        
        # Suffix for this context dataframe
        sfx = f"_{tf}"
        
        if row is None:
            # All NaN
            snapshot[f'rsi{sfx}'] = np.nan
            snapshot[f'macd_phase{sfx}'] = "UNKNOWN"
            snapshot[f'volume_rel{sfx}'] = np.nan
            # ... assume others handled by ensure_mtc_columns later
            continue
            
        # Map fields
        snapshot[f'rsi{sfx}'] = row.get('rsi', np.nan)
        snapshot[f'rsi_ema{sfx}'] = row.get('rsi_ema', np.nan)
        snapshot[f'volume_rel{sfx}'] = row.get('vol_rel', np.nan)
        snapshot[f'macd_line{sfx}'] = row.get('macd_line', np.nan)
        snapshot[f'macd_signal{sfx}'] = row.get('macd_signal', np.nan)
        snapshot[f'macd_hist{sfx}'] = row.get('macd_hist', np.nan)
        snapshot[f'trend_soul{sfx}'] = row.get('trend_soul_score', np.nan)
        snapshot[f'regime{sfx}'] = row.get('regime', "unknown")
        snapshot[f'risk_level{sfx}'] = row.get('risk_level', "unknown")
        
        # Calculated
        # ATR
        c_close = row.get('close', np.nan)
        c_atr = row.get('atr', np.nan)
        if pd.notna(c_close) and c_close > 0 and pd.notna(c_atr):
            snapshot[f'atr_pct{sfx}'] = (c_atr / c_close) * 100
        else:
            snapshot[f'atr_pct{sfx}'] = np.nan
            
        # MACD Phase
        c_hist = row.get('macd_hist', np.nan)
        if pd.notna(c_hist):
            snapshot[f'macd_phase{sfx}'] = classify_macd_phase(
                c_hist, row.get('macd_signal', 0), row.get('macd_line', 0)
            )
        else:
            snapshot[f'macd_phase{sfx}'] = "UNKNOWN"

    return snapshot


def generate_time_labs_summary(
    df_events: pd.DataFrame, 
    symbol: str, 
    timeframe: str,
    meta: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates the summary JSON structure for Time-Labs."""
    
    generated_at = get_turkey_now().isoformat()
    
    if df_events.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "generated_at": generated_at,
            "meta": {
                "total_events": 0,
                **meta
            },
            "buckets": {},
            "quality": {},
            "summary_tr": f"{symbol} için {timeframe} Time-Labs taramasında henüz anlamlı rally bulunamadı."
        }
        
    total_events = len(df_events)
    
    # Calculate Buckets
    buckets_data = {}
    valid_buckets = ["5p_10p", "10p_20p", "20p_30p", "30p_plus"]
    
    for b_name in valid_buckets:
        subset = df_events[df_events['rally_bucket'] == b_name]
        if subset.empty:
            continue
            
        b_info = {
            "event_count": len(subset),
            "avg_future_max_gain_pct": float(subset['future_max_gain_pct'].mean()),
            "avg_quality_score": float(subset['quality_score'].mean()) if 'quality_score' in subset else 0.0,
        }
        
        # Add shape ratios if available
        if 'rally_shape' in subset:
            clean_count = (subset['rally_shape'] == 'clean').sum()
            spike_count = (subset['rally_shape'] == 'spike').sum()
            if len(subset) > 0:
                b_info['clean_ratio'] = float(clean_count / len(subset))
                b_info['spike_ratio'] = float(spike_count / len(subset))
                
        buckets_data[b_name] = b_info
        
    # Calculate Overall Quality
    quality_data = {}
    if 'quality_score' in df_events:
        quality_data['avg_quality_score'] = float(df_events['quality_score'].mean())
        quality_data['high_quality_ratio'] = float((df_events['quality_score'] >= 70).sum() / total_events)
        
    if 'rally_shape' in df_events:
        shapes = df_events['rally_shape'].value_counts()
        dist = {k: float(v / total_events) for k, v in shapes.items()}
        quality_data['shape_distribution'] = dist
        
    # Generate TR Summary Text
    # "ETHUSDT için 1 saatlik Time-Labs taramasında toplam 37 rally tespit edilmiş..."
    
    # Find dominant bucket
    dominant_bucket = None
    max_c = 0
    for b_name, b_info in buckets_data.items():
        if b_info['event_count'] > max_c:
            max_c = b_info['event_count']
            dominant_bucket = b_name
            
    tf_label = {"1h": "1 saatlik", "4h": "4 saatlik"}.get(timeframe, f"{timeframe}")
    bucket_label = {"5p_10p": "%5-10", "10p_20p": "%10-20", "20p_30p": "%20-30", "30p_plus": "%30+"}.get(dominant_bucket, "")
    
    qual_score = quality_data.get('avg_quality_score', 0)
    qual_text = "düşük kalite"
    if qual_score > 60: qual_text = "orta kalite"
    if qual_score > 75: qual_text = "yüksek kalite"
    
    summary_tr = (f"{symbol} için {tf_label} Time-Labs taramasında toplam {total_events} rally tespit edilmiş.")
    if dominant_bucket:
        summary_tr += (f" Özellikle {bucket_label} aralığında, {qual_text} hareketler öne çıkıyor.")
        
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "generated_at": generated_at,
        "meta": {
            "total_events": total_events,
            **meta
        },
        "buckets": buckets_data,
        "quality": quality_data,
        "summary_tr": summary_tr
    }


def run_timeframe_rally_scan_for_symbol(
    symbol: str, 
    timeframe: str,
    lookahead: int,
    min_gain: float,
    buckets: List[float],
    event_gap: int
) -> TimeframeRallyScanResult:
    """
    Orchestrator for running a rally scan on a specific timeframe (1h/4h).
    Handles loading data, detection, enrichment, validation, and saving.
    """
    logger.info(f"=== Starting Time-Labs {timeframe} Scan for {symbol} ===")
    
    # 1. Load Data
    # Identify which timeframes we need for context
    # Always load 1h, 4h, 1d. Variable 15m.
    required_context_tfs = ["15m", "1h", "4h", "1d"]
    loaded_dfs = {}
    
    for tf in required_context_tfs:
        try:
            df = load_features(symbol, tf)
            # Ensure datetime index
            if not df.empty:
                if 'timestamp' not in df.columns:
                    # Fallback or error
                    if 'open_time' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
                    else:
                         df['timestamp'] = pd.to_datetime(df.index)
                elif df['timestamp'].dtype == 'int64':
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            loaded_dfs[tf] = df
        except Exception as e:
            logger.debug(f"Could not load {tf} for {symbol}: {e}")
            loaded_dfs[tf] = pd.DataFrame()
            
    df_main = loaded_dfs.get(timeframe)
    if df_main is None or df_main.empty:
        logger.warning(f"Main timeframe {timeframe} data missing for {symbol}")
        # Return empty result
        return _handle_empty_result(symbol, timeframe, lookahead, min_gain)

    # 2. Detect Rallies
    df_events = detect_rallies_for_timeframe(
        df_tf=df_main,
        timeframe=timeframe,
        min_gain_pct=min_gain,
        lookahead_bars=lookahead,
        buckets=buckets,
        event_gap=event_gap
    )
    
    if df_events.empty:
        return _handle_empty_result(symbol, timeframe, lookahead, min_gain)
        
    # 3. Enrich with Multi-TF Context
    enriched_rows = []
    
    for _, event in df_events.iterrows():
        idx = event['event_index']
        # Double check index bound
        if idx >= len(df_main): continue
        
        base_row = df_main.iloc[idx]
        event_time = event['event_time']
        
        snapshot = enrich_event_with_multitf_snapshot_generic(
            event_time=event_time,
            base_tf=timeframe,
            base_row=base_row,
            context_dfs=loaded_dfs
        )
        
        # Merge event info + snapshot
        row_data = event.to_dict()
        row_data.update(snapshot)
        row_data['symbol'] = symbol
        # row_data['event_tf'] = timeframe # Will be set by MTC utils anyway
        
        enriched_rows.append(row_data)
        
    df_final = pd.DataFrame(enriched_rows)
    
    # 4. Enrich with Validation (Quality Engine)
    # This adds quality_score, rally_shape etc.
    try:
        # We need prices series for quality calc
        prices = df_main.set_index('timestamp')['close']
        
        # Use default config for this timeframe
        # If not present in map, defaults to 1h settings inside engine, which is fine
        df_final = enrich_rally_events_with_quality(
            events_df=df_final,
            prices=prices,
            timeframe=timeframe
        )
        logger.info(f"Enriched with Rally v2 quality metrics")
        
    except Exception as e:
        logger.error(f"Quality enrichment failed: {e}", exc_info=True)
        # Fallback to defaults managed by validation schema or manual
    
    # 5. MTC v1 Schema Enforcement
    try:
        df_final["event_tf"] = timeframe
        
        # ensure_mtc_columns ensures we have all columns for [15m, 1h, 4h, 1d]
        # or whatever is defined as standard.
        # We enforce "15m", "1h", "4h", "1d" based on Fast15 precedent
        # But for 4h scanner, maybe we care less about 15m?
        # Let's align with "Time-Labs Standard": 15m/1h/4h/1d all included.
        req_tfs = ["15m", "1h", "4h", "1d"]
        
        df_final = ensure_mtc_columns(df_final, req_tfs)
        validate_mtc_schema(df_final, req_tfs)
        
    except Exception as e:
        logger.error(f"MTC Schema enforcement failed: {e}", exc_info=True)
        
    # 6. Save Findings
    output_path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
    df_final.to_parquet(output_path, index=False)
    
    summary = generate_time_labs_summary(
        df_final, 
        symbol, 
        timeframe, 
        meta={"lookahead_bars": lookahead, "min_gain": min_gain}
    )
    summary_path = coin_cell_paths.get_time_labs_rallies_summary_path(symbol, timeframe)
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    # Stats for return
    buckets_cnt = {k: v['event_count'] for k, v in summary['buckets'].items()}
    
    logger.info(f"Saved {len(df_final)} events to {output_path}")
    
    return TimeframeRallyScanResult(
        symbol=symbol,
        timeframe=timeframe,
        num_events_total=len(df_final),
        num_events_by_bucket=buckets_cnt,
        output_path=output_path,
        summary_path=summary_path
    )


def _handle_empty_result(symbol, timeframe, lookahead, min_gain):
    """Helper to save empty state."""
    output_path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
    summary_path = coin_cell_paths.get_time_labs_rallies_summary_path(symbol, timeframe)
    
    # Empty DF with MTC schema
    df_empty = pd.DataFrame()
    df_empty = ensure_mtc_columns(df_empty, ["15m", "1h", "4h", "1d"])
    df_empty.to_parquet(output_path, index=False)
    
    summary = generate_time_labs_summary(
        pd.DataFrame(), 
        symbol, 
        timeframe, 
        meta={"lookahead_bars": lookahead, "min_gain": min_gain}
    )
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    return TimeframeRallyScanResult(
        symbol=symbol,
        timeframe=timeframe,
        num_events_total=0,
        num_events_by_bucket={},
        output_path=output_path,
        summary_path=summary_path
    )


# --- Convenience Wrappers ---

def run_1h_rally_scan_for_symbol(symbol: str) -> TimeframeRallyScanResult:
    """Run Time-Labs scan for 1h timeframe."""
    return run_timeframe_rally_scan_for_symbol(
        symbol=symbol,
        timeframe="1h",
        lookahead=TIME_LABS_LOOKAHEAD_BARS["1h"],
        min_gain=TIME_LABS_MIN_GAIN["1h"],
        buckets=TIME_LABS_RALLY_BUCKETS,
        event_gap=TIME_LABS_EVENT_GAP["1h"]
    )


def run_4h_rally_scan_for_symbol(symbol: str) -> TimeframeRallyScanResult:
    """Run Time-Labs scan for 4h timeframe."""
    return run_timeframe_rally_scan_for_symbol(
        symbol=symbol,
        timeframe="4h",
        lookahead=TIME_LABS_LOOKAHEAD_BARS["4h"],
        min_gain=TIME_LABS_MIN_GAIN["4h"],
        buckets=TIME_LABS_RALLY_BUCKETS,
        event_gap=TIME_LABS_EVENT_GAP["4h"]
    )
