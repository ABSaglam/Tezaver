"""
Rally Quality Engine (Rally v2)
================================

This module computes advanced quality metrics for rally events, including:
- rally_shape: "clean" | "spike" | "choppy" | "weak"
- quality_score: 0-100
- Supporting metrics: drawdown, efficiency, retention

All thresholds are configurable per timeframe.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class RallyQualityConfig:
    """Configuration for rally quality assessment."""
    
    # Minimum gain to be considered a rally
    min_gain_pct: float
    
    # Clean rally criteria
    clean_min_bars: int
    clean_max_bars: int
    max_clean_drawdown_pct: float
    min_clean_efficiency: float
    min_clean_retention_ratio: float
    
    # Spike rally criteria
    max_spike_bars: int
    max_spike_retention_ratio: float
    
    # Quality score normalization targets
    target_gain_for_score: float
    max_dd_for_score: float
    
    # Retention measurement horizons
    retention_short_bars: int  # e.g., 3 bars
    retention_long_bars: int   # e.g., 10 bars
    
    # Choppy rally threshold
    choppy_efficiency_threshold: float


def get_default_rally_quality_config() -> Dict[str, RallyQualityConfig]:
    """
    Get default rally quality configurations for each timeframe.
    
    Returns:
        Dictionary mapping timeframe to RallyQualityConfig
    """
    return {
        "15m": RallyQualityConfig(
            min_gain_pct=0.05,
            clean_min_bars=2,
            clean_max_bars=8,
            max_clean_drawdown_pct=0.02,
            min_clean_efficiency=0.6,
            min_clean_retention_ratio=0.4,
            max_spike_bars=2,
            max_spike_retention_ratio=0.2,
            target_gain_for_score=0.10,
            max_dd_for_score=0.05,
            retention_short_bars=3,
            retention_long_bars=10,
            choppy_efficiency_threshold=0.6,
        ),
        "1h": RallyQualityConfig(
            min_gain_pct=0.05,
            clean_min_bars=2,
            clean_max_bars=12,
            max_clean_drawdown_pct=0.03,
            min_clean_efficiency=0.55,
            min_clean_retention_ratio=0.35,
            max_spike_bars=3,
            max_spike_retention_ratio=0.25,
            target_gain_for_score=0.15,
            max_dd_for_score=0.08,
            retention_short_bars=3,
            retention_long_bars=10,
            choppy_efficiency_threshold=0.55,
        ),
        "4h": RallyQualityConfig(
            min_gain_pct=0.08,
            clean_min_bars=2,
            clean_max_bars=15,
            max_clean_drawdown_pct=0.05,
            min_clean_efficiency=0.5,
            min_clean_retention_ratio=0.3,
            max_spike_bars=4,
            max_spike_retention_ratio=0.3,
            target_gain_for_score=0.20,
            max_dd_for_score=0.10,
            retention_short_bars=3,
            retention_long_bars=10,
            choppy_efficiency_threshold=0.5,
        ),
        "1d": RallyQualityConfig(
            min_gain_pct=0.10,
            clean_min_bars=2,
            clean_max_bars=20,
            max_clean_drawdown_pct=0.08,
            min_clean_efficiency=0.45,
            min_clean_retention_ratio=0.25,
            max_spike_bars=5,
            max_spike_retention_ratio=0.35,
            target_gain_for_score=0.30,
            max_dd_for_score=0.15,
            retention_short_bars=3,
            retention_long_bars=10,
            choppy_efficiency_threshold=0.45,
        ),
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value between min and max.
    
    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Clamped value
    """
    return max(min_val, min(value, max_val))


# ============================================================================
# CORE METRICS COMPUTATION
# ============================================================================

def compute_rally_path_metrics(
    prices: pd.Series,
    event_idx: int,
    bars_to_peak: int,
    cfg: RallyQualityConfig,
) -> Dict[str, float]:
    """
    Compute path-based rally quality metrics.
    
    Args:
        prices: Close price series (integer-indexed or datetime-indexed)
        event_idx: Index of the event bar in prices
        bars_to_peak: Number of bars from event to peak
        cfg: Rally quality configuration
        
    Returns:
        Dictionary containing:
            - net_gain_pct: Net gain from entry to peak
            - pre_peak_drawdown_pct: Maximum drawdown before peak
            - trend_efficiency: Net gain / gross path distance
            - retention_3_pct: Gain retention at short horizon
            - retention_10_pct: Gain retention at long horizon
    """
    try:
        # Get entry and peak prices
        entry_price = prices.iloc[event_idx]
        peak_idx = event_idx + bars_to_peak
        
        # Safety check
        if peak_idx >= len(prices):
            logger.warning(f"Peak index {peak_idx} exceeds price series length {len(prices)}")
            peak_idx = len(prices) - 1
        
        peak_price = prices.iloc[peak_idx]
        
        # Net gain
        net_gain_pct = (peak_price / entry_price - 1.0) if entry_price > 0 else 0.0
        
        # Trend efficiency: net gain / gross path
        gross_path_pct = 0.0
        for k in range(event_idx + 1, peak_idx + 1):
            if k < len(prices):
                delta_pct = abs(prices.iloc[k] / prices.iloc[k - 1] - 1.0)
                gross_path_pct += delta_pct
        
        trend_efficiency = (net_gain_pct / gross_path_pct) if gross_path_pct > 0 else 0.0
        
        # Pre-peak drawdown
        pre_peak_drawdown_pct = 0.0
        for k in range(event_idx, peak_idx + 1):
            if k < len(prices):
                dd_k = (prices.iloc[k] / entry_price - 1.0) if entry_price > 0 else 0.0
                pre_peak_drawdown_pct = min(pre_peak_drawdown_pct, dd_k)
        
        # Retention at short and long horizons
        retention_short_idx = min(event_idx + cfg.retention_short_bars, len(prices) - 1)
        retention_long_idx = min(event_idx + cfg.retention_long_bars, len(prices) - 1)
        
        retention_3_pct = (prices.iloc[retention_short_idx] / entry_price - 1.0) if entry_price > 0 else 0.0
        retention_10_pct = (prices.iloc[retention_long_idx] / entry_price - 1.0) if entry_price > 0 else 0.0
        
        return {
            "net_gain_pct": net_gain_pct,
            "pre_peak_drawdown_pct": pre_peak_drawdown_pct,
            "trend_efficiency": trend_efficiency,
            "retention_3_pct": retention_3_pct,
            "retention_10_pct": retention_10_pct,
        }
        
    except Exception as e:
        logger.error(f"Error computing rally path metrics: {e}", exc_info=True)
        return {
            "net_gain_pct": 0.0,
            "pre_peak_drawdown_pct": 0.0,
            "trend_efficiency": 0.0,
            "retention_3_pct": 0.0,
            "retention_10_pct": 0.0,
        }


# ============================================================================
# SHAPE CLASSIFICATION
# ============================================================================

def classify_rally_shape(
    net_gain_pct: float,
    bars_to_peak: int,
    pre_peak_drawdown_pct: float,
    trend_efficiency: float,
    retention_3_pct: float,
    retention_10_pct: float,
    cfg: RallyQualityConfig,
) -> str:
    """
    Classify rally shape based on quality metrics.
    
    Args:
        net_gain_pct: Net gain percentage
        bars_to_peak: Number of bars to peak
        pre_peak_drawdown_pct: Pre-peak drawdown (negative value)
        trend_efficiency: Trend efficiency ratio
        retention_3_pct: Retention at short horizon
        retention_10_pct: Retention at long horizon
        cfg: Rally quality configuration
        
    Returns:
        Rally shape: "clean" | "spike" | "choppy" | "weak"
    """
    # WEAK: Insufficient gain
    if net_gain_pct < cfg.min_gain_pct:
        return "weak"
    
    # CLEAN: Smooth, sustained rally
    is_clean = (
        cfg.clean_min_bars <= bars_to_peak <= cfg.clean_max_bars
        and abs(pre_peak_drawdown_pct) <= cfg.max_clean_drawdown_pct
        and trend_efficiency >= cfg.min_clean_efficiency
        and retention_10_pct >= net_gain_pct * cfg.min_clean_retention_ratio
    )
    if is_clean:
        return "clean"
    
    # SPIKE: Quick pump, poor retention
    is_spike = (
        bars_to_peak <= cfg.max_spike_bars
        and (retention_3_pct <= net_gain_pct * cfg.max_spike_retention_ratio
             or retention_3_pct < 0.0)
    )
    if is_spike:
        return "spike"
    
    # CHOPPY: Good gain but inefficient path
    if (net_gain_pct >= cfg.min_gain_pct
        and trend_efficiency < cfg.choppy_efficiency_threshold):
        return "choppy"
    
    # Fallback: Use efficiency threshold
    if trend_efficiency >= cfg.choppy_efficiency_threshold:
        return "clean"
    else:
        return "choppy"


# ============================================================================
# QUALITY SCORE
# ============================================================================

def compute_quality_score(
    net_gain_pct: float,
    pre_peak_drawdown_pct: float,
    trend_efficiency: float,
    retention_10_pct: float,
    cfg: RallyQualityConfig,
) -> float:
    """
    Compute overall quality score (0-100).
    
    Score components:
    - Gain component (0-30): Based on net gain vs target
    - Efficiency component (0-30): Based on trend efficiency
    - Retention component (0-25): Based on long-term retention
    - Drawdown component (0-15): Based on pre-peak drawdown
    
    Args:
        net_gain_pct: Net gain percentage
        pre_peak_drawdown_pct: Pre-peak drawdown (negative value)
        trend_efficiency: Trend efficiency ratio
        retention_10_pct: Retention at long horizon
        cfg: Rally quality configuration
        
    Returns:
        Quality score between 0 and 100
    """
    # Gain component (0-30)
    gain_norm = clamp(net_gain_pct / cfg.target_gain_for_score, 0, 1)
    gain_score = gain_norm * 30.0
    
    # Efficiency component (0-30)
    # Map efficiency from [0.3, 0.7] to [0, 1]
    eff_norm = (trend_efficiency - 0.3) / (0.7 - 0.3)
    eff_norm = clamp(eff_norm, 0, 1)
    eff_score = eff_norm * 30.0
    
    # Retention component (0-25)
    if net_gain_pct > 0:
        ret_ratio = clamp(retention_10_pct / net_gain_pct, 0, 1)
    else:
        ret_ratio = 0.0
    ret_score = ret_ratio * 25.0
    
    # Drawdown component (0-15)
    dd_norm = 1.0 - abs(pre_peak_drawdown_pct) / cfg.max_dd_for_score
    dd_norm = clamp(dd_norm, 0, 1)
    dd_score = dd_norm * 15.0
    
    # Total score
    total_score = gain_score + eff_score + ret_score + dd_score
    total_score = clamp(total_score, 0, 100)
    
    return round(total_score, 1)


# ============================================================================
# HIGH-LEVEL ENRICHMENT API
# ============================================================================

def enrich_rally_events_with_quality(
    events_df: pd.DataFrame,
    prices: pd.Series,
    timeframe: str,
    cfg_map: Optional[Dict[str, RallyQualityConfig]] = None,
) -> pd.DataFrame:
    """
    Enrich rally events DataFrame with quality metrics.
    
    Args:
        events_df: DataFrame with rally events containing:
            - event_time (datetime): Event timestamp
            - bars_to_peak (int): Bars from event to peak
            - future_max_gain_pct (float): Maximum future gain
        prices: Close price series (datetime-indexed)
        timeframe: Timeframe string ("15m", "1h", "4h", "1d")
        cfg_map: Optional custom config map (uses defaults if None)
        
    Returns:
        Copy of events_df with added columns:
            - rally_shape
            - quality_score
            - pre_peak_drawdown_pct
            - trend_efficiency
            - retention_3_pct
            - retention_10_pct
    """
    if events_df.empty:
        logger.warning("Empty events DataFrame provided")
        return events_df.copy()
    
    # Get configuration
    cfg_map = cfg_map or get_default_rally_quality_config()
    if timeframe not in cfg_map:
        logger.warning(f"No config for timeframe {timeframe}, using 15m defaults")
        timeframe = "15m"
    cfg = cfg_map[timeframe]
    
    # Make a copy
    df = events_df.copy()
    
    # Initialize new columns
    df["rally_shape"] = "unknown"
    df["quality_score"] = 0.0
    df["pre_peak_drawdown_pct"] = 0.0
    df["trend_efficiency"] = 0.0
    df["retention_3_pct"] = 0.0
    df["retention_10_pct"] = 0.0
    
    # Ensure prices has datetime index for alignment
    if not isinstance(prices.index, pd.DatetimeIndex):
        logger.warning("Prices series must have DatetimeIndex for proper alignment")
        return df
    
    # Process each event
    for idx, row in df.iterrows():
        try:
            event_time = row["event_time"]
            bars_to_peak = int(row["bars_to_peak"]) if "bars_to_peak" in row else 0
            
            # Find event index in prices
            if event_time not in prices.index:
                # Try to find nearest timestamp
                nearest_idx = prices.index.get_indexer([event_time], method="nearest")[0]
                if nearest_idx == -1:
                    logger.warning(f"Cannot align event at {event_time} to price series")
                    continue
                event_idx = nearest_idx
            else:
                event_idx = prices.index.get_loc(event_time)
            
            # Compute metrics
            metrics = compute_rally_path_metrics(
                prices=prices,
                event_idx=event_idx,
                bars_to_peak=bars_to_peak,
                cfg=cfg,
            )
            
            # Classify shape
            shape = classify_rally_shape(
                net_gain_pct=metrics["net_gain_pct"],
                bars_to_peak=bars_to_peak,
                pre_peak_drawdown_pct=metrics["pre_peak_drawdown_pct"],
                trend_efficiency=metrics["trend_efficiency"],
                retention_3_pct=metrics["retention_3_pct"],
                retention_10_pct=metrics["retention_10_pct"],
                cfg=cfg,
            )
            
            # Compute quality score
            score = compute_quality_score(
                net_gain_pct=metrics["net_gain_pct"],
                pre_peak_drawdown_pct=metrics["pre_peak_drawdown_pct"],
                trend_efficiency=metrics["trend_efficiency"],
                retention_10_pct=metrics["retention_10_pct"],
                cfg=cfg,
            )
            
            # Update DataFrame
            df.at[idx, "rally_shape"] = shape
            df.at[idx, "quality_score"] = score
            df.at[idx, "pre_peak_drawdown_pct"] = metrics["pre_peak_drawdown_pct"]
            df.at[idx, "trend_efficiency"] = metrics["trend_efficiency"]
            df.at[idx, "retention_3_pct"] = metrics["retention_3_pct"]
            df.at[idx, "retention_10_pct"] = metrics["retention_10_pct"]
            
        except Exception as e:
            logger.warning(f"Error enriching event at index {idx}: {e}")
            continue
    
    return df
