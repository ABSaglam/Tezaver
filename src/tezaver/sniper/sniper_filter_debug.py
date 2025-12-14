"""
Sniper Filter Debug Module
===========================

Provides debugging info to explain why Sniper trades are missing/low.
Shows filter stages, drop counts, and effective config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pandas as pd


@dataclass
class SniperFilterStageCount:
    """Count at each filter stage."""
    stage: str           # "TOTAL", "RSI", "VOL", "ATR", "QUALITY", "ML"
    count: int           # Number of entries after this filter
    ratio: float         # Ratio vs total (count / initial_total)
    dropped: int = 0     # Number dropped by this stage


@dataclass
class SniperFilterDebugInfo:
    """Debug info for Sniper filter pipeline."""
    stages: List[SniperFilterStageCount]
    effective_filters: Dict[str, Any]
    data_stats: Dict[str, Any]
    bottleneck_stage: Optional[str] = None  # Stage that drops most entries
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stages": [asdict(s) for s in self.stages],
            "effective_filters": self.effective_filters,
            "data_stats": self.data_stats,
            "bottleneck_stage": self.bottleneck_stage,
        }


@dataclass
class SniperEntrySelection:
    """Result of entry selection."""
    selected_df: pd.DataFrame
    debug_info: Optional[SniperFilterDebugInfo] = None
    selection_mode: str = "UNKNOWN"
    count: int = 0


def select_sniper_entries(
    df: pd.DataFrame,
    mode: str,  # "CARD_STRICT_IDS" or "ARENA_FILTERS"
    card: Dict[str, Any],
    effective_window: Dict[str, Any],
) -> SniperEntrySelection:
    """
    Select entries based on mode.
    
    Args:
        df: Full sniper entries dataframe
        mode: Selection mode
        card: Strategy card (for provenance IDs)
        effective_window: Effective filter window (for ARENA_FILTERS)
        
    Returns:
        SniperEntrySelection with selected subset and debug info.
    """
    if df is None or df.empty:
        return SniperEntrySelection(pd.DataFrame(), None, mode, 0)
    
    # Mode 1: CARD_STRICT_IDS (Static from provenance)
    if "CARD_STRICT_IDS" in mode:
        provenance = card.get("provenance", {})
        strict_ids = set(provenance.get("strict_entry_ids", []))
        
        # Helper to generate ID
        def make_key(row):
            eid = str(row.get("event_id", ""))
            ts = str(row.get("event_time", row.get("ts", "")))[:19]
            return f"{eid}|{ts}"
            
        # Filter DF
        if strict_ids:
            mask = df.apply(lambda row: make_key(row) in strict_ids, axis=1)
            selected_df = df[mask].copy()
        else:
            selected_df = pd.DataFrame()
            
        return SniperEntrySelection(
            selected_df=selected_df,
            debug_info=None,
            selection_mode="CARD_STRICT_IDS",
            count=len(selected_df)
        )

    # Mode 2: ARENA_FILTERS (Dynamic via effective window)
    debug_info = compute_sniper_filter_debug(df, effective_window)
    
    current_df = df.copy()
    entry_filters = effective_window.get("entry_filters", {})
    
    # RSI
    rsi_cfg = entry_filters.get("rsi", {})
    if rsi_cfg.get("enabled", True):
        rsi_col = "feat_rsi_14" if "feat_rsi_14" in current_df.columns else "rsi"
        if rsi_col in current_df.columns:
            top = rsi_cfg.get("max", 100)
            bot = rsi_cfg.get("min", 0)
            current_df = current_df[(current_df[rsi_col] >= bot) & (current_df[rsi_col] <= top)]
            
    # VOLUME
    vol_cfg = entry_filters.get("volume", {})
    if vol_cfg.get("enabled", True):
        vol_col = "feat_volume_ratio" if "feat_volume_ratio" in current_df.columns else "volume"
        if vol_col in current_df.columns:
            bot = vol_cfg.get("min", 0)
            current_df = current_df[current_df[vol_col] >= bot]
            
    # ATR
    atr_cfg = entry_filters.get("atr", {})
    if atr_cfg.get("enabled", True):
        atr_col = "feat_atr_14" if "feat_atr_14" in current_df.columns else "atr"
        if atr_col in current_df.columns:
            val = current_df[atr_col]
            top = atr_cfg.get("max")
            bot = atr_cfg.get("min", 0)
            if top is not None:
                current_df = current_df[(val >= bot) & (val <= top)]
            else:
                current_df = current_df[val >= bot]

    # QUALITY
    q_cfg = entry_filters.get("quality", {})
    if q_cfg.get("enabled", True):
        q_col = "feat_quality_score" if "feat_quality_score" in current_df.columns else "quality_score"
        if q_col in current_df.columns:
            bot = q_cfg.get("min", 0)
            current_df = current_df[current_df[q_col] >= bot]
            
    # ML - currently assumed applied if toggle is on (placeholder for actual ML inference)
    
    # PATTERN Rules
    pattern_rules = effective_window.get("pattern_rules", [])
    pattern_enabled = effective_window.get("pattern_enabled", False)
    
    if pattern_enabled and pattern_rules:
        for rule in pattern_rules:
            feat = rule.get("feature")
            min_v = rule.get("min")
            max_v = rule.get("max")
            enabled = rule.get("enabled", True)
            
            if not feat or not enabled:
                continue
            
            col = f"feat_{feat}" if f"feat_{feat}" in current_df.columns else feat
            if col in current_df.columns:
                if min_v is not None:
                    current_df = current_df[current_df[col] >= min_v]
                if max_v is not None:
                    current_df = current_df[current_df[col] <= max_v]
    
    return SniperEntrySelection(
        selected_df=current_df,
        debug_info=debug_info,
        selection_mode="ARENA_FILTERS",
        count=len(current_df)
    )


def compute_sniper_filter_debug(
    df: pd.DataFrame,
    effective_cfg: Dict[str, Any],
) -> SniperFilterDebugInfo:
    """
    Apply filters stage-by-stage and compute counts at each stage.
    
    Args:
        df: Sniper entries dataframe
        effective_cfg: Effective filter configuration
        
    Returns:
        SniperFilterDebugInfo with stage counts and bottleneck analysis.
    """
    if df is None or df.empty:
        return SniperFilterDebugInfo(
            stages=[SniperFilterStageCount("TOTAL", 0, 0.0, 0)],
            effective_filters=effective_cfg,
            data_stats={"total_entries": 0, "date_range": "-"},
            bottleneck_stage="NO_DATA",
        )
    
    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]
    
    initial_total = len(df)
    stages: List[SniperFilterStageCount] = []
    
    # Stage 0: TOTAL
    stages.append(SniperFilterStageCount(
        stage="TOTAL",
        count=initial_total,
        ratio=1.0,
        dropped=0,
    ))
    
    current_df = df.copy()
    prev_count = initial_total
    
    # Get filters from config
    entry_filters = effective_cfg.get("entry_filters", {})
    
    # Stage 1: RSI Filter
    rsi_filter = entry_filters.get("rsi", {})
    if rsi_filter.get("enabled", True):
        rsi_min = rsi_filter.get("min", 0)
        rsi_max = rsi_filter.get("max", 100)
        rsi_col = "feat_rsi_14" if "feat_rsi_14" in current_df.columns else "rsi"
        
        if rsi_col in current_df.columns:
            mask = (current_df[rsi_col] >= rsi_min) & (current_df[rsi_col] <= rsi_max)
            current_df = current_df[mask]
    
    count_after_rsi = len(current_df)
    stages.append(SniperFilterStageCount(
        stage="RSI",
        count=count_after_rsi,
        ratio=count_after_rsi / initial_total if initial_total > 0 else 0,
        dropped=prev_count - count_after_rsi,
    ))
    prev_count = count_after_rsi
    
    # Stage 2: Volume Filter
    vol_filter = entry_filters.get("volume", {})
    if vol_filter.get("enabled", True):
        vol_min = vol_filter.get("min", 0)
        vol_col = "feat_volume_ratio" if "feat_volume_ratio" in current_df.columns else "volume"
        
        if vol_col in current_df.columns:
            mask = current_df[vol_col] >= vol_min
            current_df = current_df[mask]
    
    count_after_vol = len(current_df)
    stages.append(SniperFilterStageCount(
        stage="VOLUME",
        count=count_after_vol,
        ratio=count_after_vol / initial_total if initial_total > 0 else 0,
        dropped=prev_count - count_after_vol,
    ))
    prev_count = count_after_vol
    
    # Stage 3: ATR Filter
    atr_filter = entry_filters.get("atr", {})
    if atr_filter.get("enabled", True):
        atr_min = atr_filter.get("min", 0)
        atr_max = atr_filter.get("max", 999)
        atr_col = "feat_atr_14" if "feat_atr_14" in current_df.columns else "atr"
        
        if atr_col in current_df.columns:
            mask = (current_df[atr_col] >= atr_min) & (current_df[atr_col] <= atr_max)
            current_df = current_df[mask]
    
    count_after_atr = len(current_df)
    stages.append(SniperFilterStageCount(
        stage="ATR",
        count=count_after_atr,
        ratio=count_after_atr / initial_total if initial_total > 0 else 0,
        dropped=prev_count - count_after_atr,
    ))
    prev_count = count_after_atr
    
    # Stage 4: Quality Filter
    quality_filter = entry_filters.get("quality", {})
    if quality_filter.get("enabled", True):
        quality_min = quality_filter.get("min", 0)
        quality_col = "feat_quality_score" if "feat_quality_score" in current_df.columns else "quality_score"
        
        if quality_col in current_df.columns:
            mask = current_df[quality_col] >= quality_min
            current_df = current_df[mask]
    
    count_after_quality = len(current_df)
    stages.append(SniperFilterStageCount(
        stage="QUALITY",
        count=count_after_quality,
        ratio=count_after_quality / initial_total if initial_total > 0 else 0,
        dropped=prev_count - count_after_quality,
    ))
    prev_count = count_after_quality
    
    # Stage 5: ML Filter (if present)
    ml_filters = effective_cfg.get("ml_filters", {})
    if ml_filters.get("enabled", False):
        ml_threshold = ml_filters.get("threshold", 0.5)
        ml_col = "ml_score" if "ml_score" in current_df.columns else None
        
        if ml_col and ml_col in current_df.columns:
            mask = current_df[ml_col] >= ml_threshold
            current_df = current_df[mask]
    
    count_after_ml = len(current_df)
    stages.append(SniperFilterStageCount(
        stage="ML",
        count=count_after_ml,
        ratio=count_after_ml / initial_total if initial_total > 0 else 0,
        dropped=prev_count - count_after_ml,
    ))
    prev_count = count_after_ml
    
    # Stage 6: PATTERN Rules (NEW)
    pattern_rules = effective_cfg.get("pattern_rules", [])
    pattern_enabled = effective_cfg.get("pattern_enabled", False)
    
    if pattern_enabled and pattern_rules:
        for rule in pattern_rules:
            feat = rule.get("feature")
            min_v = rule.get("min")
            max_v = rule.get("max")
            enabled = rule.get("enabled", True)
            
            if not feat or not enabled:
                continue
            
            col = f"feat_{feat}" if f"feat_{feat}" in current_df.columns else feat
            if col in current_df.columns:
                if min_v is not None:
                    current_df = current_df[current_df[col] >= min_v]
                if max_v is not None:
                    current_df = current_df[current_df[col] <= max_v]
    
    count_after_pattern = len(current_df)
    stages.append(SniperFilterStageCount(
        stage="PATTERN",
        count=count_after_pattern,
        ratio=count_after_pattern / initial_total if initial_total > 0 else 0.0,
        dropped=prev_count - count_after_pattern,
    ))
    
    # Find bottleneck (stage that drops most)
    max_dropped = 0
    bottleneck = None
    for stage in stages[1:]:  # Skip TOTAL
        if stage.dropped > max_dropped:
            max_dropped = stage.dropped
            bottleneck = stage.stage
    
    # Data stats
    data_stats = {
        "total_entries": initial_total,
        "selected_entries": count_after_pattern,
        "filter_pass_rate": f"{count_after_pattern / initial_total * 100:.1f}%" if initial_total > 0 else "0%",
    }
    
    # Date range from data
    ts_col = None
    for c in ["event_time", "ts", "timestamp"]:
        if c in df.columns:
            ts_col = c
            break
    
    if ts_col:
        try:
            dates = pd.to_datetime(df[ts_col])
            data_stats["date_range"] = f"{dates.min().strftime('%Y-%m-%d')} → {dates.max().strftime('%Y-%m-%d')}"
            data_stats["span_days"] = (dates.max() - dates.min()).days
        except:
            data_stats["date_range"] = "-"
    
    return SniperFilterDebugInfo(
        stages=stages,
        effective_filters=effective_cfg,
        data_stats=data_stats,
        bottleneck_stage=bottleneck,
    )


# =============================================================================
# DATASET STATS
# =============================================================================

@dataclass
class SniperDatasetStats:
    """Statistics for dataset columns."""
    rsi_min: float = 0.0
    rsi_max: float = 100.0
    rsi_p05: float = 0.0
    rsi_p95: float = 100.0
    
    volume_min: float = 0.0
    volume_max: float = 10.0
    volume_p05: float = 0.0
    volume_p95: float = 10.0
    
    atr_min: float = 0.0
    atr_max: float = 100.0
    atr_p05: float = 0.0
    atr_p95: float = 100.0
    
    quality_min: float = 0.0
    quality_max: float = 100.0
    quality_p05: float = 0.0
    quality_p95: float = 100.0


def compute_sniper_dataset_stats(df: pd.DataFrame) -> SniperDatasetStats:
    """
    Compute min/max and p05/p95 percentiles for filter columns.
    """
    if df is None or df.empty:
        return SniperDatasetStats()
    
    stats = SniperDatasetStats()
    
    # RSI
    rsi_col = "feat_rsi_14" if "feat_rsi_14" in df.columns else "rsi"
    if rsi_col in df.columns:
        vals = df[rsi_col].dropna()
        if len(vals) > 0:
            stats.rsi_min = float(vals.min())
            stats.rsi_max = float(vals.max())
            stats.rsi_p05 = float(vals.quantile(0.05))
            stats.rsi_p95 = float(vals.quantile(0.95))
    
    # Volume
    vol_col = "feat_volume_ratio" if "feat_volume_ratio" in df.columns else "volume"
    if vol_col in df.columns:
        vals = df[vol_col].dropna()
        if len(vals) > 0:
            stats.volume_min = float(vals.min())
            stats.volume_max = float(vals.max())
            stats.volume_p05 = float(vals.quantile(0.05))
            stats.volume_p95 = float(vals.quantile(0.95))
    
    # ATR
    atr_col = "feat_atr_14" if "feat_atr_14" in df.columns else "atr"
    if atr_col in df.columns:
        vals = df[atr_col].dropna()
        if len(vals) > 0:
            stats.atr_min = float(vals.min())
            stats.atr_max = float(vals.max())
            stats.atr_p05 = float(vals.quantile(0.05))
            stats.atr_p95 = float(vals.quantile(0.95))
    
    # Quality
    q_col = "feat_quality_score" if "feat_quality_score" in df.columns else "quality_score"
    if q_col in df.columns:
        vals = df[q_col].dropna()
        if len(vals) > 0:
            stats.quality_min = float(vals.min())
            stats.quality_max = float(vals.max())
            stats.quality_p05 = float(vals.quantile(0.05))
            stats.quality_p95 = float(vals.quantile(0.95))
    
    return stats


# =============================================================================
# EFFECTIVE FILTER WINDOW (Tightness Interpolation)
# =============================================================================

def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation: t=0 → a, t=1 → b."""
    return a + (b - a) * t


def build_effective_sniper_filter_window(
    profile_cfg: Dict[str, Any],
    tightness: int,  # 0-100
    toggles: Dict[str, bool],  # {"rsi": True, "volume": True, ...}
    dataset_stats: SniperDatasetStats,
    clamp_policy: str = "HARD",  # "OFF" | "SOFT" | "HARD"
    quality_override: Optional[float] = None,  # Manual override for quality min
) -> Dict[str, Any]:
    """
    Build effective filter config based on tightness.
    
    tightness=100 → use profile config exactly
    tightness=0 → use dataset global min/max (most relaxed) + ML disabled
    
    Clamp Policy for QUALITY:
    - OFF: No floor, interpolation result as-is
    - SOFT: Floor interpolates from dataset_min (at t=0) to 50 (at t=1)
    - HARD: Floor is always 50 (current behavior)
    
    Args:
        profile_cfg: Original config from profile/card
        tightness: 0-100 slider value
        toggles: Per-filter enable/disable
        dataset_stats: Stats from compute_sniper_dataset_stats
        clamp_policy: "OFF" | "SOFT" | "HARD"
        quality_override: Optional manual override for quality min
        
    Returns:
        Effective config dict with interpolated filter windows.
    """
    t = tightness / 100.0  # Normalize to 0-1
    
    # Base filters from profile
    entry_filters = profile_cfg.get("entry_filters", {})
    
    # RSI filter
    rsi_cfg = entry_filters.get("rsi", {})
    rsi_profile_min = rsi_cfg.get("min", 20)
    rsi_profile_max = rsi_cfg.get("max", 80)
    
    effective_rsi = {
        "enabled": toggles.get("rsi", True),
        "min": _lerp(dataset_stats.rsi_min, rsi_profile_min, t),
        "max": _lerp(dataset_stats.rsi_max, rsi_profile_max, t),
    }
    
    # Volume filter
    vol_cfg = entry_filters.get("volume", {})
    vol_profile_min = vol_cfg.get("min", 1.0)
    
    effective_vol = {
        "enabled": toggles.get("volume", True),
        "min": _lerp(dataset_stats.volume_min, vol_profile_min, t),
    }
    
    # ATR filter
    atr_cfg = entry_filters.get("atr", {})
    atr_profile_min = atr_cfg.get("min", 0)
    atr_profile_max = atr_cfg.get("max", 999)
    
    effective_atr = {
        "enabled": toggles.get("atr", True),
        "min": _lerp(dataset_stats.atr_min, atr_profile_min, t),
        "max": _lerp(dataset_stats.atr_max, atr_profile_max, t),
    }
    
    # Quality filter with Clamp Policy
    q_cfg = entry_filters.get("quality", {})
    q_profile_min = q_cfg.get("min", 50)
    
    # Step 1: Interpolate based on tightness
    q_interpolated_min = _lerp(dataset_stats.quality_min, q_profile_min, t)
    
    # Step 2: Apply clamp policy
    quality_min_before_clamp = q_interpolated_min
    
    if quality_override is not None:
        # Manual override takes precedence
        q_effective_min = quality_override
    elif clamp_policy == "OFF":
        # No floor, use interpolation result as-is
        q_effective_min = q_interpolated_min
    elif clamp_policy == "SOFT":
        # Floor interpolates: dataset_min (t=0) → 50 (t=1)
        floor = _lerp(dataset_stats.quality_min, 50.0, t)
        q_effective_min = max(q_interpolated_min, floor)
    else:  # HARD (default)
        # Floor is always 50
        q_effective_min = max(q_interpolated_min, 50.0)
    
    quality_min_after_clamp = q_effective_min
    
    effective_quality = {
        "enabled": toggles.get("quality", True),
        "min": q_effective_min,
        "min_before_clamp": quality_min_before_clamp,
        "min_after_clamp": quality_min_after_clamp,
        "clamp_policy": clamp_policy,
        "override": quality_override,
    }
    
    # ML filters - disabled when tightness < 40
    ml_enabled = toggles.get("ml", tightness >= 40)
    
    # Pattern Rules
    pattern_cfg = profile_cfg.get("pattern_rules_v1", {})
    # Pattern toggle (defaults to True if rules exist, unless toggled off)
    pattern_enabled = toggles.get("pattern", True)
    
    return {
        "entry_filters": {
            "rsi": effective_rsi,
            "volume": effective_vol,
            "atr": effective_atr,
            "quality": effective_quality,
        },
        "ml_filters": {
            "enabled": ml_enabled,
            "threshold": profile_cfg.get("ml_filters", {}).get("threshold", 0.5),
        },
        "pattern_rules": pattern_cfg.get("rules", []),
        "pattern_enabled": pattern_enabled,
        "tightness": tightness,
        "clamp_policy": clamp_policy,
        "quality_override": quality_override,
    }


# =============================================================================
# AUTO-RELAX SUGGESTION
# =============================================================================

@dataclass
class RelaxSuggestion:
    """Suggestion for relaxing a filter."""
    stage: str
    current_min: float
    current_max: float
    suggested_min: float
    suggested_max: float
    expected_keep_pct: float


def suggest_relaxation(
    debug_info: SniperFilterDebugInfo,
    df: pd.DataFrame,
    current_window: Dict[str, Any],
    target_keep_ratio: float = 0.8,
) -> Optional[RelaxSuggestion]:
    """
    Suggest filter relaxation based on bottleneck.
    
    Args:
        debug_info: Current debug info with bottleneck identified
        df: Original dataset
        current_window: Current effective filter config
        target_keep_ratio: Target ratio to keep (e.g., 0.8 = keep 80%)
        
    Returns:
        RelaxSuggestion if relaxation is possible, None otherwise.
    """
    if not debug_info.bottleneck_stage:
        return None
    
    if df is None or df.empty:
        return None
    
    stage = debug_info.bottleneck_stage
    entry_filters = current_window.get("entry_filters", {})
    
    # Find percentile that would keep target_keep_ratio
    low_pct = (1 - target_keep_ratio) / 2 * 100  # e.g., 10 for 80% keep
    high_pct = 100 - low_pct  # e.g., 90
    
    if stage == "RSI":
        col = "feat_rsi_14" if "feat_rsi_14" in df.columns else "rsi"
        if col not in df.columns:
            return None
        vals = df[col].dropna()
        current = entry_filters.get("rsi", {})
        return RelaxSuggestion(
            stage="RSI",
            current_min=current.get("min", 0),
            current_max=current.get("max", 100),
            suggested_min=float(vals.quantile(low_pct / 100)),
            suggested_max=float(vals.quantile(high_pct / 100)),
            expected_keep_pct=target_keep_ratio * 100,
        )
    
    elif stage == "VOLUME":
        col = "feat_volume_ratio" if "feat_volume_ratio" in df.columns else "volume"
        if col not in df.columns:
            return None
        vals = df[col].dropna()
        current = entry_filters.get("volume", {})
        return RelaxSuggestion(
            stage="VOLUME",
            current_min=current.get("min", 0),
            current_max=999.0,
            suggested_min=float(vals.quantile(low_pct / 100)),
            suggested_max=float(vals.quantile(high_pct / 100)),
            expected_keep_pct=target_keep_ratio * 100,
        )
    
    elif stage == "ATR":
        col = "feat_atr_14" if "feat_atr_14" in df.columns else "atr"
        if col not in df.columns:
            return None
        vals = df[col].dropna()
        current = entry_filters.get("atr", {})
        return RelaxSuggestion(
            stage="ATR",
            current_min=current.get("min", 0),
            current_max=current.get("max", 999),
            suggested_min=float(vals.quantile(low_pct / 100)),
            suggested_max=float(vals.quantile(high_pct / 100)),
            expected_keep_pct=target_keep_ratio * 100,
        )
    
    elif stage == "QUALITY":
        col = "feat_quality_score" if "feat_quality_score" in df.columns else "quality_score"
        if col not in df.columns:
            return None
        vals = df[col].dropna()
        current = entry_filters.get("quality", {})
        return RelaxSuggestion(
            stage="QUALITY",
            current_min=current.get("min", 0),
            current_max=100.0,
            suggested_min=float(vals.quantile(low_pct / 100)),
            suggested_max=100.0,
            expected_keep_pct=target_keep_ratio * 100,
        )
    
    return None
