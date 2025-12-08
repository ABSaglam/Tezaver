
"""
Rally Radar Engine (Core)
=========================

This module implements the core logic for "Rally Radar v1".
It analyzes multi-timeframe rally events and strategy signals to generate a comprehensive
coin profile describing the "environment status" (HOT/COLD/NEUTRAL/CHAOTIC) and
strategy affinity/promotion status.

Features:
- Configurable environment scoring (Events, Quality, Clarity, Trend).
- Status determination logic.
- Integration with Sim Affinity & Promotion layers.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import (
    get_fast15_rallies_path,
    get_time_labs_rallies_path,
    get_coin_profile_dir,
    get_sim_promotion_path
)

logger = get_logger(__name__)


# --- Configuration ---

@dataclass
class RallyRadarConfig:
    """Configuration for Rally Radar scoring and thresholds."""
    
    # Data Window
    lookback_days: Dict[str, int] = field(default_factory=lambda: {
        "15m": 7,
        "1h": 30,
        "4h": 60
    })
    
    # Minimum events to be considered valid data
    min_events_required: Dict[str, int] = field(default_factory=lambda: {
        "15m": 20,
        "1h": 15,
        "4h": 10
    })
    
    # Scoring Weights (Sum = 100 approx)
    weight_density: float = 30.0
    weight_quality: float = 30.0
    weight_clarity: float = 25.0
    weight_trend: float = 15.0
    
    # Status Thresholds (Environment Score 0-100)
    threshold_hot: float = 70.0
    threshold_neutral: float = 40.0
    # < 40 is COLD
    
    # Chaos / Quality Filters
    spike_ratio_max_chaotic: float = 0.40  # If > 40% spikes, CHAOTIC
    clarity_min_chaotic: float = 0.40      # If clarity index < 0.4, CHAOTIC
    
    # Trend alignment thresholds
    trend_soul_strong: float = 60.0


def get_default_rally_radar_config() -> RallyRadarConfig:
    return RallyRadarConfig()


# --- Dataclasses ---

@dataclass
class RallyRadarTimeframeStats:
    """Statistics and status for a single timeframe."""
    status: str  # HOT, NEUTRAL, COLD, CHAOTIC, NO_DATA
    environment_score: float # 0-100
    
    event_count: int
    clean_ratio: float
    spike_ratio: float
    
    avg_quality_score: float
    avg_future_max_gain_pct: float
    avg_retention_10_pct: float
    
    clarity_index: float
    
    trend_context: Dict[str, Any] = field(default_factory=dict)
    strategy_layer: Dict[str, Any] = field(default_factory=dict) # Enriched later
    flags: List[str] = field(default_factory=list)


@dataclass
class RallyRadarProfile:
    """Full Rally Radar profile for a coin."""
    symbol: str
    version: str = "1.0"
    generated_at: str = "" # ISO string
    
    meta: Dict[str, Any] = field(default_factory=dict)
    
    # Results per TF
    timeframes: Dict[str, RallyRadarTimeframeStats] = field(default_factory=dict)
    
    # Overall synthesized result
    overall: Dict[str, Any] = field(default_factory=dict)


# --- Data Loading ---

def load_rally_events_for_tf(symbol: str, tf: str, cfg: RallyRadarConfig) -> pd.DataFrame:
    """
    Load rally events for a specific symbol and timeframe, filtered by lookback.
    Returns empty DataFrame if file not found or empty.
    """
    try:
        # Resolve path based on TF
        if tf == "15m":
            # Fast15 uses parquet output
            # Note: get_fast15_rallies_path logic differs slightly for 'all' vs 'symbol'
            # But the core function returns the file path.
            # Assuming standard naming: data/coin_cells/{SYMBOL}/rallies/fast15_rallies.parquet
            # Let's use the helper.
            path = get_fast15_rallies_path(symbol)
        elif tf in ["1h", "4h"]:
            # Time-Labs uses parquet too: time_labs_{tf}_rallies.parquet
            path = get_time_labs_rallies_path(symbol, tf)
        else:
            logger.warning(f"Unknown timeframe for Rally Radar: {tf}")
            return pd.DataFrame()
        
        if not path.exists():
            return pd.DataFrame()
            
        df = pd.read_parquet(path)
        if df.empty:
            return pd.DataFrame()
            
        # Filter by lookback
        days = cfg.lookback_days.get(tf, 30)
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Ensure event_time is datetime
        if 'event_time' in df.columns:
            df['event_time'] = pd.to_datetime(df['event_time'])
            df = df[df['event_time'] >= cutoff]
            
        return df
        
    except Exception as e:
        logger.warning(f"Error loading rally events for {symbol} {tf}: {e}")
        return pd.DataFrame()


# --- Core Computation ---

def compute_timeframe_stats(
    df_events: pd.DataFrame, 
    tf: str, 
    cfg: RallyRadarConfig
) -> RallyRadarTimeframeStats:
    """
    Compute environment stats and status for a single timeframe DataFrame.
    """
    flags = []
    
    # 1. Handle Empty / Insufficient Data
    if df_events.empty:
        flags.append("NO_DATA")
        return RallyRadarTimeframeStats(
            status="NO_DATA",
            environment_score=0.0,
            event_count=0,
            clean_ratio=0.0, spike_ratio=0.0,
            avg_quality_score=0.0, avg_future_max_gain_pct=0.0, avg_retention_10_pct=0.0,
            clarity_index=0.0,
            flags=flags
        )

    # 2. Basic Metrics
    total = len(df_events)
    
    # Metric: Clean/Spike Ratio
    # Check column existence to be safe
    if 'rally_shape' in df_events.columns:
        counts = df_events['rally_shape'].value_counts(normalize=True)
        clean_ratio = counts.get('clean', 0.0)
        spike_ratio = counts.get('spike', 0.0)
    else:
        clean_ratio = 0.0
        spike_ratio = 0.0
        
    # Metric: Quality & Gain
    avg_quality = df_events['quality_score_v2'].mean() if 'quality_score_v2' in df_events.columns else 0.0
    avg_gain = df_events['future_max_gain_pct'].mean() if 'future_max_gain_pct' in df_events.columns else 0.0
    avg_retention = df_events['retention_10_pct'].mean() if 'retention_10_pct' in df_events.columns else 0.0
    
    # 3. Clarity Index
    # Formula: 0.5 * Clean + 0.3 * (1 - Spike) + 0.2 * (Quality/100)
    clarity_index = (0.5 * clean_ratio) + (0.3 * (1.0 - spike_ratio)) + (0.2 * (avg_quality / 100.0))
    
    # 4. Trend Context (from latest events)
    # We take the mean of the last N events to get "recent context"
    # Or mean of the whole window? Implementation plan said "mean".
    trend_ctx = {}
    trend_score_val = 0.0 # 0-1
    
    if 'trend_soul_4h' in df_events.columns:
        t4h = df_events['trend_soul_4h'].mean()
        trend_ctx['trend_soul_4h_mean'] = float(t4h)
        if t4h >= cfg.trend_soul_strong:
            flags.append("STRONG_UPTREND_4H")
        elif t4h <= 40:
             pass # Weak
    
    if 'trend_soul_1d' in df_events.columns:
        t1d = df_events['trend_soul_1d'].mean()
        trend_ctx['trend_soul_1d_mean'] = float(t1d)
        
    if 'rsi_1d' in df_events.columns:
        rsi = df_events['rsi_1d'].mean()
        trend_ctx['rsi_1d_mean'] = float(rsi)
        
    # Trend Alignment Score (Simplified)
    # If 4h trend > 50 -> +0.5
    # If 1d trend > 50 -> +0.3
    # RSI not extreme -> +0.2
    
    t_score = 0.0
    val_t4h = trend_ctx.get('trend_soul_4h_mean', 50)
    val_t1d = trend_ctx.get('trend_soul_1d_mean', 50)
    val_rsi = trend_ctx.get('rsi_1d_mean', 50)
    
    if val_t4h > 55: t_score += 0.5
    if val_t1d > 55: t_score += 0.3
    if 40 <= val_rsi <= 75: t_score += 0.2
    
    trend_alignment_score = min(1.0, t_score)
    
    # 5. Density Score
    # Logarithmic or linear saturation? Linear saturated at 2x min required is simple.
    req = cfg.min_events_required.get(tf, 10)
    if total < req:
        # Insufficient data to be confident
        flags.append("LOW_DATA")
        density_score = total / req # Linear ramp up to 1.0
    else:
        # Logic: If we have 2x required, we are fully dense (1.0)
        density_score = min(1.0, total / (req * 2.0))
        
    # 6. Environment Score Calculation
    # Normalize inputs to 0-1 range roughly
    # density_score (0-1) created above
    # quality_score_norm (0-1)
    # clarity_index (0-1)
    # trend_alignment_score (0-1)
    
    quality_norm = min(1.0, avg_quality / 100.0)
    
    env_score = (
        (cfg.weight_density * density_score) +
        (cfg.weight_quality * quality_norm) +
        (cfg.weight_clarity * clarity_index) +
        (cfg.weight_trend * trend_alignment_score)
    )
    
    # 7. Status Determination
    if total < req:
        status = "NO_DATA" # Or strictly "LOW_DATA"? Prompt said "NO_DATA" logic for empty, but < min_events -> NO_DATA usually safer.
        # Let's say NO_DATA/INSUFFICIENT
        status = "NO_DATA" 
    elif spike_ratio > cfg.spike_ratio_max_chaotic:
        status = "CHAOTIC"
        flags.append("HIGH_SPIKE_RATIO")
    elif clarity_index < cfg.clarity_min_chaotic:
        status = "CHAOTIC"
        flags.append("LOW_CLARITY")
    else:
        if env_score >= cfg.threshold_hot:
            status = "HOT"
        elif env_score >= cfg.threshold_neutral:
            status = "NEUTRAL"
        else:
            status = "COLD"

    return RallyRadarTimeframeStats(
        status=status,
        environment_score=float(env_score),
        event_count=int(total),
        clean_ratio=float(clean_ratio),
        spike_ratio=float(spike_ratio),
        avg_quality_score=float(avg_quality),
        avg_future_max_gain_pct=float(avg_gain),
        avg_retention_10_pct=float(avg_retention),
        clarity_index=float(clarity_index),
        trend_context=trend_ctx,
        flags=flags
    )


def enrich_with_strategy_layer(
    stats_by_tf: Dict[str, RallyRadarTimeframeStats],
    symbol: str,
    cfg: RallyRadarConfig
) -> None:
    """
    Enrich the stats with Strategy Promotion data (Sim v1.5).
    Modifies stats_by_tf in-place.
    """
    try:
        # Load promotion data
        # We need data/coin_profiles/{SYMBOL}/sim_promotion.json
        # Ideally using a helper or just direct path
        path = get_sim_promotion_path(symbol)
        
        if not path.exists():
            return
            
        with open(path, 'r', encoding='utf-8') as f:
            promo_data = json.load(f)
            
        strategies = promo_data.get("strategies", {})
        if not strategies:
            return
            
        # Map Presets to Timeframes
        # This mapping should ideally be in Config or Registry, but hardcoding for v1 as per instruction
        # "FAST15_" -> "15m", "H1_" -> "1h", "H4_" -> "4h"
        
        for pid, s_data in strategies.items():
            tf_target = None
            if "FAST15_" in pid: tf_target = "15m"
            elif "H1_" in pid: tf_target = "1h"
            elif "H4_" in pid: tf_target = "4h"
            
            if tf_target and tf_target in stats_by_tf:
                st_layer = stats_by_tf[tf_target].strategy_layer
                
                # We categorize into 'approved_presets' and 'candidate_presets' lists in the dict
                if "approved_presets" not in st_layer: st_layer["approved_presets"] = []
                if "candidate_presets" not in st_layer: st_layer["candidate_presets"] = []
                
                status = s_data.get("status")
                reliability = s_data.get("reliability")
                item = {
                    "preset_id": pid,
                    "affinity_score": s_data.get("affinity_score"),
                    "grade": s_data.get("grade"),
                    "reliability": reliability
                }
                
                if status == "APPROVED":
                    st_layer["approved_presets"].append(item)
                elif status == "CANDIDATE":
                    st_layer["candidate_presets"].append(item)
                    
    except Exception as e:
        logger.warning(f"Error enriching strategy layer for {symbol}: {e}")


# --- Profile Building ---

def build_rally_radar_profile(
    symbol: str, 
    now: Optional[datetime] = None,
    cfg: Optional[RallyRadarConfig] = None
) -> RallyRadarProfile:
    """
    Build the full Rally Radar profile for a symbol.
    """
    if cfg is None:
        cfg = get_default_rally_radar_config()
        
    if now is None:
        now = datetime.utcnow()
        
    # 1. Compute Stats per TF
    stats_map = {}
    timeframes = ["15m", "1h", "4h"]
    
    for tf in timeframes:
        df = load_rally_events_for_tf(symbol, tf, cfg)
        stats = compute_timeframe_stats(df, tf, cfg)
        stats_map[tf] = stats
        
    # 2. Enrich with Strategy Layer
    enrich_with_strategy_layer(stats_map, symbol, cfg)
    
    # 3. Overall Synthesis
    # Determine Dominant Lane
    # Rule: HOT TF with APPROVED strategy > HOT TF with highest Env Score > None
    
    hot_tfs = [tf for tf, s in stats_map.items() if s.status == "HOT"]
    
    dominant_lane = "NONE"
    best_lane_score = -1.0
    
    # First pass: Look for HOT + APPROVED
    candidate_lanes = []
    for tf in hot_tfs:
        layer = stats_map[tf].strategy_layer
        approved = layer.get("approved_presets", [])
        if approved:
            # Get max affinity score
            max_aff = max([x.get("affinity_score", 0) for x in approved])
            candidate_lanes.append((tf, max_aff))
            
    if candidate_lanes:
        # Pick TF with highest affinity score
        candidate_lanes.sort(key=lambda x: x[1], reverse=True)
        dominant_lane = candidate_lanes[0][0]
    elif hot_tfs:
        # Second pass: Just highest Env Score
        # Sort by env score
        hot_tfs.sort(key=lambda tf: stats_map[tf].environment_score, reverse=True)
        dominant_lane = hot_tfs[0]
        
    # Determine Overall Status
    # Priority: 4h > 1h > 15m
    overall_status = "NEUTRAL" # Default fallback
    
    s4h = stats_map["4h"].status
    s1h = stats_map["1h"].status
    s15m = stats_map["15m"].status
    
    if s4h == "HOT":
        overall_status = "HOT"
    elif s1h == "HOT":
        overall_status = "HOT"
    elif s4h == "COLD" and s1h == "COLD" and s15m == "COLD":
        overall_status = "COLD"
    elif "CHAOTIC" in [s4h, s1h, s15m]:
        # If higher TFs are chaotic, it's risky
        if s4h == "CHAOTIC":
            overall_status = "CHAOTIC"
        else:
            overall_status = "NEUTRAL" # Mixed signals usually neutral/wait
    else:
        overall_status = "NEUTRAL"
        
    # Meta
    meta = {
        "lookback_days": cfg.lookback_days,
        "config_thresholds": {
            "hot": cfg.threshold_hot,
            "neutral": cfg.threshold_neutral
        }
    }
    
    return RallyRadarProfile(
        symbol=symbol,
        generated_at=now.isoformat(),
        meta=meta,
        timeframes=stats_map,
        overall={
            "dominant_lane": dominant_lane,
            "overall_status": overall_status
        }
    )


# --- Persistence ---

def save_rally_radar_profile(symbol: str, profile: RallyRadarProfile) -> Path:
    """Save profile to JSON."""
    profile_dir = get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    path = profile_dir / "rally_radar.json"
    
    data = asdict(profile)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return path
