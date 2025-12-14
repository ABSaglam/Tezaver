"""
Sniper Strategy Card Builder
=============================

Builds ML-derived strategy cards from sniper pattern insights.
Extracts entry filters (RSI, ATR, volume ranges) with good_rate lift.

Output: data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional

import json
import numpy as np
import pandas as pd

from tezaver.sniper.sniper_pattern_miner import (
    run_sniper_pattern_miner_for_symbol_timeframe,
)
from tezaver.sniper.sniper_annotations import SniperAnnotationRepository


# =============================================================================
# Constants
# =============================================================================

DEFAULT_MIN_SUPPORT = 3        # min samples for a bin to be considered
DEFAULT_MIN_LIFT = 0.10        # good_rate must be +10% above baseline


# =============================================================================
# Config
# =============================================================================

@dataclass
class StrictSelectionConfig:
    """Configuration for strict selection expansion."""
    enabled: bool = True
    method: str = "HYBRID"  # AUTO_RELAX, SIMILARITY_TOPK, SIMILARITY_CUTOFF, HYBRID
    min_strict_count: int = 10
    topk: int = None  # Default: min_strict_count
    distance_cutoff: float = None  # None = no cutoff
    feature_weights: dict = None  # Default weights
    normalize: str = "zscore"  # zscore normalization
    seed_policy: dict = None  # statuses, labels, min_seed_count
    
    def __post_init__(self):
        if self.topk is None:
            self.topk = self.min_strict_count
        if self.feature_weights is None:
            self.feature_weights = {
                "rsi_15m": 1.0,
                "volume_rel_15m": 1.0,
                "atr_pct_15m": 1.0,
                "quality_score": 0.5,
            }
        if self.seed_policy is None:
            self.seed_policy = {
                "use_statuses": ["APPROVED"],
                "use_labels": ["GOOD"],
                "min_seed_count": 3,
            }


@dataclass
class StrictQualityContract:
    """Quality contract for strict selection - enforces quality thresholds."""
    min_strict_count: int = 10
    max_distance_p50: float = None  # e.g., 3.0 - None means no limit
    max_distance_p90: float = None  # e.g., 4.5 - None means no limit
    max_auto_relax_ratio: float = 0.5  # Max 50% of strict can be AUTO_RELAX
    min_seed_count: int = 3
    enforce_mode: str = "WARN"  # WARN or BLOCK
    
    def check_violations(self, strict_selection: dict, strict_count: int) -> dict:
        """
        Check contract against actual results.
        Returns: {"ok": bool, "violations": [...], "suggested_actions": [...]}
        """
        violations = []
        suggestions = []
        
        seed_count = strict_selection.get("seed_count", 0)
        distance_stats = strict_selection.get("distance_stats", {})
        p50 = distance_stats.get("p50")
        p90 = distance_stats.get("p90")
        
        # Count selection types
        details = strict_selection.get("strict_selection_details", [])
        if not details:
            # Fallback: use the outer provenance details if passed
            pass
        
        auto_relax_count = sum(1 for d in details if d.get("selected_by") == "AUTO_RELAX")
        auto_relax_ratio = auto_relax_count / max(1, strict_count)
        
        # Check min_seed_count
        if seed_count < self.min_seed_count:
            violations.append({
                "code": "SEED_SHORTAGE",
                "actual": seed_count,
                "expected": f">= {self.min_seed_count}",
            })
            suggestions.append("Add more APPROVED+GOOD annotations")
        
        # Check min_strict_count
        if strict_count < self.min_strict_count:
            violations.append({
                "code": "STRICT_COUNT_LOW",
                "actual": strict_count,
                "expected": f">= {self.min_strict_count}",
            })
            suggestions.append("Increase distance_cutoff or switch to HYBRID method")
        
        # Check max_distance_p50
        if self.max_distance_p50 is not None and p50 is not None and p50 > self.max_distance_p50:
            violations.append({
                "code": "P50_TOO_HIGH",
                "actual": p50,
                "expected": f"<= {self.max_distance_p50}",
            })
            suggestions.append("Lower feature weights or add more seed entries")
        
        # Check max_distance_p90
        if self.max_distance_p90 is not None and p90 is not None and p90 > self.max_distance_p90:
            violations.append({
                "code": "P90_TOO_HIGH",
                "actual": p90,
                "expected": f"<= {self.max_distance_p90}",
            })
            suggestions.append("Use distance_cutoff to exclude outliers")
        
        # Check auto_relax_ratio
        if auto_relax_ratio > self.max_auto_relax_ratio:
            violations.append({
                "code": "AUTO_RELAX_RATIO_HIGH",
                "actual": round(auto_relax_ratio, 3),
                "expected": f"<= {self.max_auto_relax_ratio}",
            })
            suggestions.append("Switch to SIMILARITY method or improve seed quality")
        
        return {
            "ok": len(violations) == 0,
            "violations": violations,
            "suggested_actions": suggestions,
            "auto_relax_count": auto_relax_count,
            "auto_relax_ratio": round(auto_relax_ratio, 4),
        }


@dataclass
class SniperStrategyCardConfig:
    """Configuration for strategy card building."""
    symbol: str
    timeframe: str = "15m"
    min_support: int = DEFAULT_MIN_SUPPORT
    min_lift: float = DEFAULT_MIN_LIFT
    top_features_limit: int = 6
    
    # Filter parameters for source set creation (UI-controlled)
    include_grades: list = None  # Default: ["SILVER"]
    include_status: list = None  # Default: ["APPROVED"]
    include_labels: list = None  # Default: ["GOOD"]
    quality_floor_policy: str = "HARD"  # OFF, SOFT, HARD
    quality_floor_value: float = 50.0
    
    # Strict selection config (replaces simple similarity_enabled)
    strict_selection: StrictSelectionConfig = None
    
    # Quality contract for strict selection
    strict_contract: StrictQualityContract = None
    
    # Legacy compatibility fields
    similarity_enabled: bool = True
    min_strict_count: int = 10
    
    def __post_init__(self):
        if self.include_grades is None:
            self.include_grades = ["SILVER"]
        if self.include_status is None:
            self.include_status = ["APPROVED"]
        if self.include_labels is None:
            self.include_labels = ["GOOD"]
        if self.strict_selection is None:
            # Build from legacy fields
            self.strict_selection = StrictSelectionConfig(
                enabled=self.similarity_enabled,
                min_strict_count=self.min_strict_count,
            )
        if self.strict_contract is None:
            self.strict_contract = StrictQualityContract()



# =============================================================================
# Loaders
# =============================================================================

def _load_sniper_dataset(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    """Load sniper entries dataset."""
    base = Path("data/ai_datasets") / symbol.upper() / timeframe
    path = base / "sniper_entries_v1.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Sniper dataset not found at {path}")
    return pd.read_parquet(path)


def _load_or_compute_insights(
    symbol: str,
    timeframe: str = "15m",
) -> Dict[str, Any]:
    """Load cached insights or compute fresh."""
    base = Path("data/ai_insights") / symbol.upper() / timeframe
    path = base / "sniper_pattern_insights_v1.json"
    
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    
    # Compute if not exists
    summary = run_sniper_pattern_miner_for_symbol_timeframe(symbol, timeframe)
    base.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


# =============================================================================
# Entry Filter Builder
# =============================================================================

def _parse_bin_string(bin_str: str) -> Optional[tuple]:
    """Parse bin string like '(30.5, 45.2]' to (min, max)."""
    try:
        # Remove brackets and parentheses
        raw = bin_str.strip()
        raw = raw.replace("[", "").replace("]", "").replace("(", "").replace(")", "")
        parts = raw.split(",")
        if len(parts) != 2:
            return None
        min_val = float(parts[0].strip())
        max_val = float(parts[1].strip())
        return (min_val, max_val)
    except Exception:
        return None


def _build_entry_filters_from_insights(
    insights: Dict[str, Any],
    cfg: SniperStrategyCardConfig,
) -> Dict[str, Any]:
    """
    Extract entry filters from top features and their best bins.
    
    For each feature, select bin(s) that have:
    - min_support samples
    - good_rate > global_positive_rate + min_lift
    """
    positive_rate = float(insights.get("positive_rate", 0.0))
    feature_bins = insights.get("feature_bins", {})
    top_features = insights.get("top_features", [])

    entry_filters: Dict[str, Any] = {}
    feature_meta: Dict[str, Any] = {}
    pattern_rules: List[Dict[str, Any]] = []

    # Limit features
    feat_order = top_features[:cfg.top_features_limit] if top_features else list(feature_bins.keys())[:cfg.top_features_limit]

    for feat in feat_order:
        bins_info = feature_bins.get(feat)
        if not bins_info:
            continue
        bins = bins_info.get("bins", [])
        if not bins:
            continue

        # Find bins with sufficient support and lift
        good_bins: List[Dict[str, Any]] = []
        for b in bins:
            count = int(b.get("count", 0))
            good_rate = float(b.get("good_rate", 0.0))
            
            if count < cfg.min_support:
                continue
            
            lift = good_rate - positive_rate
            if lift < cfg.min_lift:
                continue
            
            # Store lift for sorting
            b["lift"] = lift
            b["rate"] = good_rate
            b["neg"] = count - int(count * good_rate)
            b["pos"] = int(count * good_rate)
            good_bins.append(b)

        if not good_bins:
            continue

        # Sort by lift, select best
        good_bins.sort(key=lambda x: x["lift"], reverse=True)
        best = good_bins[0]
        
        # Parse bin range
        bin_label = best.get("bin_label") or best.get("bin", "")
        parsed = _parse_bin_string(bin_label)
        if parsed is None:
            feature_meta[feat] = {
                "selected_bin": best,
                "parse_error": True,
            }
            continue

        min_val, max_val = parsed
        entry_filters[feat] = {
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "source": "sniper_pattern_bin_v1",
        }
        feature_meta[feat] = {
            "selected_bin": best,
            "global_positive_rate": round(positive_rate, 4),
        }
        
        # Add to pattern rules
        pattern_rules.append({
            "feature": feat,
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "support": best.get("pos", 0) + best.get("neg", 0),
            "good_rate": round(best.get("rate", 0.0), 4),
            "lift": round(best.get("lift", 0.0), 4),
            "source": "sniper_pattern_insights_v1",
        })

    return {
        "entry_filters": entry_filters,
        "feature_meta": feature_meta,
        "pattern_rules": pattern_rules,
        "positive_rate": positive_rate,
    }


# =============================================================================
# Card Builder
# =============================================================================

def build_sniper_strategy_card_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
    cfg: Optional[SniperStrategyCardConfig] = None,
) -> Dict[str, Any]:
    """
    Build sniper strategy card from insights.
    
    Returns:
        Dictionary with version, entry_filters, feature_meta, labels, provenance.
    """
    from datetime import datetime
    
    symbol = symbol.upper()
    if cfg is None:
        cfg = SniperStrategyCardConfig(symbol=symbol, timeframe=timeframe)

    # Load data
    df = _load_sniper_dataset(symbol, timeframe)
    insights = _load_or_compute_insights(symbol, timeframe)

    # Build filters
    filters_obj = _build_entry_filters_from_insights(insights, cfg)
    entry_filters = filters_obj["entry_filters"]
    
    # =========================================================================
    # PROVENANCE V2.3: Actual filtering by annotations, status, label, quality
    # =========================================================================
    
    # Generate unique entry key for each row (MUST match arena_v4._ensure_trade_id)
    def _to_iso(ts) -> str:
        """Convert timestamp to ISO format string (matches arena_v4)."""
        if ts is None:
            return ""
        if isinstance(ts, str):
            return ts.replace(" ", "T")[:19]
        return str(ts)[:19].replace(" ", "T")
    
    # Detect ID column (consistent with arena_v4)
    id_col = None
    for c in ["event_idx", "event_id", "entry_id"]:
        if c in df.columns:
            id_col = c
            break
    
    ts_col = "event_time" if "event_time" in df.columns else "ts"
    
    def make_entry_key(row, idx):
        event_id = str(row.get(id_col, idx)) if id_col else str(idx)
        ts = _to_iso(row.get(ts_col, ""))
        return f"{event_id}|{ts}"
    
    # =========================================================================
    # Step 1: Load annotations and join to dataframe
    # =========================================================================
    repo = SniperAnnotationRepository()
    annotations = repo.load_all(symbol, timeframe)
    
    # Build annotation lookup by event_id
    ann_map: Dict[str, Dict[str, str]] = {}
    for ann in annotations:
        ann_map[str(ann.event_id)] = {
            "status": ann.status,
            "label": ann.label,
        }
    
    # Add annotation columns to df (default: PENDING/UNCERTAIN for unannotated)
    df = df.copy()
    
    # For annotation matching, use event_time (same format as annotation event_id)
    def get_ann_key(row, idx):
        """Get key for annotation lookup - should match annotation event_id format."""
        # Annotations store event_time directly (e.g., "2024-03-05 19:45:00")
        if ts_col in row and row[ts_col]:
            return str(row[ts_col])[:19]  # First 19 chars: "YYYY-MM-DD HH:MM:SS"
        return str(idx)
    
    def get_ann_status(row, idx):
        eid = get_ann_key(row, idx)
        return ann_map.get(eid, {}).get("status", "PENDING")
    
    def get_ann_label(row, idx):
        eid = get_ann_key(row, idx)
        return ann_map.get(eid, {}).get("label", "UNCERTAIN")
    
    df["ann_status"] = [get_ann_status(row, idx) for idx, row in df.iterrows()]
    df["ann_label"] = [get_ann_label(row, idx) for idx, row in df.iterrows()]
    
    total_entries = len(df)
    
    # =========================================================================
    # Step 2: Apply status/label filtering to get SOURCE set
    # =========================================================================
    allowed_statuses = set(cfg.include_status)
    allowed_labels = set(cfg.include_labels)
    
    df_source = df[df["ann_status"].isin(allowed_statuses)]
    after_status_count = len(df_source)
    df_source = df_source[df_source["ann_label"].isin(allowed_labels)]
    after_label_count = len(df_source)
    
    status_label_drop = total_entries - after_label_count
    
    # Track source_count BEFORE quality floor (for invariants)
    source_pre_quality_count = len(df_source)
    
    # =========================================================================
    # Step 3: Apply quality floor filtering on SOURCE set -> quality_df
    # =========================================================================
    qual_col = None
    for c in ["feat_quality_score", "quality_score"]:
        if c in df_source.columns:
            qual_col = c
            break
    
    quality_df = df_source.copy()
    quality_floor_drop = 0
    
    if cfg.quality_floor_policy in ("HARD", "SOFT") and qual_col:
        quality_df = quality_df[quality_df[qual_col] >= cfg.quality_floor_value]
        quality_floor_drop = source_pre_quality_count - len(quality_df)
    
    quality_count = len(quality_df)
    
    # Generate entry IDs from quality_df (this is source_entry_ids)
    source_entry_ids = [make_entry_key(row, idx) for idx, row in quality_df.iterrows()]
    source_count = len(source_entry_ids)  # Same as quality_count
    
    # =========================================================================
    # Step 4: Apply strict window filters on quality_df -> strict_df
    # =========================================================================
    MIN_STRICT_COUNT = 10
    QUALITY_CLAMP_VALUE = 50.0
    
    # Track clamps applied
    clamps_applied = {}
    
    # Build effective entry_filters with clamps
    effective_entry_filters = {}
    for feat_name, feat_cfg in entry_filters.items():
        feat_min = feat_cfg.get("min")
        feat_max = feat_cfg.get("max")
        
        # Apply quality clamp for entry_filter quality min
        if "quality" in feat_name.lower() and feat_min is not None:
            if feat_min < QUALITY_CLAMP_VALUE:
                clamps_applied["quality_entry_filter"] = {
                    "original_min": feat_min,
                    "clamped_min": QUALITY_CLAMP_VALUE,
                }
                feat_min = QUALITY_CLAMP_VALUE
        
        effective_entry_filters[feat_name] = {"min": feat_min, "max": feat_max}
    
    def apply_strict_filters(df_in, filters, widen_factor=1.0):
        """Apply strict window filters with optional widening."""
        result_df = df_in.copy()
        
        for feat_name, feat_cfg in filters.items():
            if feat_name not in result_df.columns:
                col_name = f"feat_{feat_name}" if f"feat_{feat_name}" in result_df.columns else None
                if col_name is None:
                    continue
            else:
                col_name = feat_name
            
            feat_min = feat_cfg.get("min")
            feat_max = feat_cfg.get("max")
            
            if widen_factor > 1.0 and feat_min is not None and feat_max is not None:
                # Widen the range
                center = (feat_min + feat_max) / 2
                half_range = (feat_max - feat_min) / 2
                widened_half = half_range * widen_factor
                feat_min = center - widened_half
                feat_max = center + widened_half
            
            if feat_min is not None:
                result_df = result_df[result_df[col_name] >= feat_min]
            if feat_max is not None:
                result_df = result_df[result_df[col_name] <= feat_max]
        
        return result_df
    
    # Initial strict filtering (threshold-based)
    strict_df = apply_strict_filters(quality_df, effective_entry_filters, widen_factor=1.0)
    strict_count = len(strict_df)
    initial_strict_count = strict_count
    threshold_strict_ids = set(make_entry_key(row, idx) for idx, row in strict_df.iterrows())
    
    # =========================================================================
    # Step 5: Strict Selection v2.7 (Weighted Similarity + Methods)
    # =========================================================================
    import numpy as np
    
    ssc = cfg.strict_selection  # StrictSelectionConfig
    MIN_STRICT = ssc.min_strict_count
    
    # Seed policy: determine which entries are seeds
    seed_statuses = set(ssc.seed_policy.get("use_statuses", ["APPROVED"]))
    seed_labels = set(ssc.seed_policy.get("use_labels", ["GOOD"]))
    min_seed_count = ssc.seed_policy.get("min_seed_count", 3)
    
    # Build seed_df based on seed_policy
    seed_df = quality_df[
        (quality_df["ann_status"].isin(seed_statuses)) &
        (quality_df["ann_label"].isin(seed_labels))
    ]
    seed_count = len(seed_df)
    seed_ids = set(make_entry_key(row, idx) for idx, row in seed_df.iterrows())
    seed_ids_sample = list(seed_ids)[:5]
    
    # Track strict_selection for provenance v2.7
    strict_selection = {
        "enabled": ssc.enabled,
        "method": "THRESHOLD",  # Will be updated
        "min_strict_count": MIN_STRICT,
        "topk": ssc.topk,
        "distance_cutoff": ssc.distance_cutoff,
        "feature_weights": ssc.feature_weights,
        "normalize": ssc.normalize,
        "seed_policy": ssc.seed_policy,
        "seed_count": seed_count,
        "seed_ids_sample": seed_ids_sample,
        "initial_strict_count": initial_strict_count,
        "achieved_count": initial_strict_count,
        "cutoff_rejected_count": 0,
        "strict_added_count": 0,
    }
    
    # Track selection details
    selection_details = []
    distance_stats = {}
    strict_added_ids_sample = []
    
    def compute_weighted_distances(df_pool, df_seed, feature_weights, normalize="zscore"):
        """
        Compute weighted L2 distances to seed centroid.
        Returns: (distances Series, available features list, centroid dict)
        """
        # Map feature names to actual columns
        feature_cols = {}
        for f in feature_weights.keys():
            for col in [f"feat_{f}", f]:
                if col in df_pool.columns:
                    feature_cols[f] = col
                    break
        
        if len(feature_cols) < 2:
            return pd.Series(dtype=float), [], {}
        
        # Extract data
        pool_data = df_pool[[feature_cols[f] for f in feature_cols]].copy()
        seed_data = df_seed[[feature_cols[f] for f in feature_cols]].copy()
        
        # Handle missing values
        pool_data = pool_data.fillna(pool_data.mean())
        seed_data = seed_data.fillna(pool_data.mean())
        
        # Z-score normalize
        means = pool_data.mean()
        stds = pool_data.std().replace(0, 1) + 1e-9
        pool_normalized = (pool_data - means) / stds
        seed_normalized = (seed_data - means) / stds
        
        # Compute centroid from seed
        centroid = seed_normalized.mean()
        
        # Compute weighted L2 distance
        weights = np.array([feature_weights.get(f, 1.0) for f in feature_cols])
        diff = pool_normalized.values - centroid.values
        weighted_sq = (diff ** 2) * weights
        distances = pd.Series(np.sqrt(weighted_sq.sum(axis=1)), index=df_pool.index)
        
        return distances, list(feature_cols.keys()), centroid.to_dict()
    
    def apply_auto_relax(df_src, entry_filters, target_count):
        """AUTO_RELAX: widen thresholds to reach target."""
        widen_factors = [1.5, 2.0, 3.0]
        result_df = df_src.copy()
        
        for wf in widen_factors:
            result_df = apply_strict_filters(df_src, entry_filters, widen_factor=wf)
            if len(result_df) >= target_count:
                break
        
        return result_df
    
    # Determine method and execute
    actual_method = ssc.method if ssc.enabled else "THRESHOLD"
    
    # If seed shortage, fallback to AUTO_RELAX
    if ssc.enabled and seed_count < min_seed_count and actual_method in ("SIMILARITY_TOPK", "SIMILARITY_CUTOFF", "HYBRID"):
        actual_method = "AUTO_RELAX"
        strict_selection["note"] = f"seed_shortage_{seed_count}<{min_seed_count}"
    
    if actual_method in ("SIMILARITY_TOPK", "SIMILARITY_CUTOFF", "HYBRID") and seed_count >= min_seed_count:
        # Compute weighted distances
        distances, features_used, centroid = compute_weighted_distances(
            quality_df, seed_df, ssc.feature_weights, ssc.normalize
        )
        
        if len(distances) > 0:
            # Compute distance stats
            distance_stats = {
                "min": round(float(distances.min()), 4),
                "p25": round(float(distances.quantile(0.25)), 4),
                "p50": round(float(distances.quantile(0.50)), 4),
                "p75": round(float(distances.quantile(0.75)), 4),
                "p90": round(float(distances.quantile(0.90)), 4),
                "max": round(float(distances.max()), 4),
            }
            
            # Add distance column
            quality_df_dist = quality_df.copy()
            quality_df_dist["_distance"] = distances
            
            # Apply method
            cutoff_rejected_count = 0
            
            if actual_method == "SIMILARITY_TOPK":
                sorted_df = quality_df_dist.sort_values("_distance")
                strict_df = sorted_df.head(ssc.topk)
                
            elif actual_method == "SIMILARITY_CUTOFF":
                if ssc.distance_cutoff is not None:
                    valid_df = quality_df_dist[quality_df_dist["_distance"] <= ssc.distance_cutoff]
                    cutoff_rejected_count = len(quality_df_dist) - len(valid_df)
                    
                    if len(valid_df) >= MIN_STRICT:
                        strict_df = valid_df.sort_values("_distance")
                    else:
                        # Fallback to AUTO_RELAX
                        strict_df = apply_auto_relax(quality_df, effective_entry_filters, MIN_STRICT)
                        actual_method = "AUTO_RELAX"
                        strict_selection["note"] = "cutoff_insufficient_fallback"
                else:
                    sorted_df = quality_df_dist.sort_values("_distance")
                    strict_df = sorted_df.head(ssc.topk)
                    
            elif actual_method == "HYBRID":
                # First: select by cutoff
                if ssc.distance_cutoff is not None:
                    cutoff_df = quality_df_dist[quality_df_dist["_distance"] <= ssc.distance_cutoff]
                    cutoff_rejected_count = len(quality_df_dist) - len(cutoff_df)
                else:
                    cutoff_df = quality_df_dist.copy()
                
                # Then: fill remaining quota with topk
                cutoff_sorted = cutoff_df.sort_values("_distance")
                
                if len(cutoff_sorted) >= MIN_STRICT:
                    strict_df = cutoff_sorted.head(MIN_STRICT)
                else:
                    # Need more: take from rejected but closest
                    remaining_needed = MIN_STRICT - len(cutoff_sorted)
                    beyond_cutoff = quality_df_dist[~quality_df_dist.index.isin(cutoff_df.index)]
                    beyond_sorted = beyond_cutoff.sort_values("_distance")
                    extras = beyond_sorted.head(remaining_needed)
                    
                    strict_df = pd.concat([cutoff_sorted, extras])
                    strict_selection["note"] = f"hybrid_filled_{len(extras)}_beyond_cutoff"
            
            strict_selection["cutoff_rejected_count"] = cutoff_rejected_count
            strict_count = len(strict_df)
            
            # Build selection details (up to 50 entries)
            for idx, row in strict_df.head(50).iterrows():
                entry_id = make_entry_key(row, idx)
                is_seed = entry_id in seed_ids
                was_threshold = entry_id in threshold_strict_ids
                dist_val = row.get("_distance", 0)
                
                if is_seed:
                    selected_by = "SEED"
                elif was_threshold:
                    selected_by = "THRESHOLD"
                else:
                    selected_by = "SIMILARITY"
                
                detail = {
                    "trade_id": entry_id,
                    "is_seed": is_seed,
                    "was_threshold_strict": was_threshold,
                    "selected_by": selected_by,
                    "distance": round(float(dist_val), 4) if pd.notna(dist_val) else None,
                }
                
                # Add feature values
                for f in features_used:
                    for col in [f"feat_{f}", f]:
                        if col in row:
                            detail[f] = round(float(row[col]), 4) if pd.notna(row[col]) else None
                            break
                
                selection_details.append(detail)
            
            # Track similarity-added IDs
            for idx, row in strict_df.iterrows():
                entry_id = make_entry_key(row, idx)
                if entry_id not in seed_ids and entry_id not in threshold_strict_ids:
                    strict_added_ids_sample.append(entry_id)
                    if len(strict_added_ids_sample) >= 20:
                        break
            
            # Drop distance column
            strict_df = strict_df.drop(columns=["_distance"], errors="ignore")
            
            strict_selection.update({
                "method": actual_method,
                "features_used": features_used,
                "achieved_count": strict_count,
                "distance_stats": distance_stats,
                "strict_added_count": len(strict_added_ids_sample),
                "strict_added_ids_sample": strict_added_ids_sample,
            })
            
    elif actual_method == "AUTO_RELAX" and strict_count < MIN_STRICT:
        strict_df = apply_auto_relax(quality_df, effective_entry_filters, MIN_STRICT)
        strict_count = len(strict_df)
        
        # Build selection details for AUTO_RELAX
        for idx, row in strict_df.head(50).iterrows():
            entry_id = make_entry_key(row, idx)
            detail = {
                "trade_id": entry_id,
                "is_seed": entry_id in seed_ids,
                "was_threshold_strict": entry_id in threshold_strict_ids,
                "selected_by": "AUTO_RELAX",
                "distance": None,
            }
            selection_details.append(detail)
        
        strict_selection.update({
            "method": "AUTO_RELAX",
            "achieved_count": strict_count,
        })
    
    elif not ssc.enabled:
        strict_selection["note"] = "similarity_disabled"
    
    
    strict_entry_ids = [make_entry_key(row, idx) for idx, row in strict_df.iterrows()]
    strict_count = len(strict_entry_ids)
    
    # =========================================================================
    # Drop Invariants - ASSERT
    # =========================================================================
    # Invariant: 0 <= strict_count <= quality_count <= source_pre_quality_count
    if not (0 <= strict_count <= quality_count <= source_pre_quality_count):
        raise RuntimeError(
            f"Drop invariant violated: strict={strict_count}, quality={quality_count}, "
            f"source_pre_quality={source_pre_quality_count}"
        )
    
    # Calculate drops with invariant check
    d1 = quality_floor_drop  # source_pre_quality -> quality
    d2 = quality_count - strict_count  # quality -> strict
    d_total = source_pre_quality_count - strict_count
    
    if d_total != d1 + d2:
        raise RuntimeError(
            f"Drop breakdown invariant violated: d_total={d_total} != d1={d1} + d2={d2}"
        )
    
    # For provenance, use quality_count as source_count (after quality floor)
    source_to_quality_drop = d1
    quality_to_strict_drop = d2
    source_to_strict_drop = d_total
    strict_window_drop = d2  # legacy
    
    # Bottleneck detection
    if source_to_quality_drop > quality_to_strict_drop and source_to_quality_drop > 0:
        bottleneck = "SOURCE_TO_QUALITY"
    elif quality_to_strict_drop > source_to_quality_drop and quality_to_strict_drop > 0:
        bottleneck = "QUALITY_TO_STRICT"
    elif source_to_quality_drop == quality_to_strict_drop and source_to_quality_drop > 0:
        bottleneck = "TIE"
    else:
        bottleneck = "NONE"
    
    # Strict window details
    strict_keep_ratio = strict_count / max(1, quality_count)
    strict_window_details = {
        "effective_filters": effective_entry_filters,
        "strict_keep_ratio": round(strict_keep_ratio, 4),
        "min_strict_threshold": MIN_STRICT,
    }
    
    # Build provenance object v2.7 with weighted similarity diagnostics
    provenance = {
        "version": "v2.7",
        "total_entries": total_entries,
        "source_count": source_count,  # after quality floor
        "quality_count": quality_count,
        "strict_count": strict_count,
        "strict_drop_count": strict_window_drop,  # legacy field for compatibility
        "drops": {
            "status_label_drop": status_label_drop,
            "quality_floor_drop": quality_floor_drop,
            "strict_window_drop": strict_window_drop,
        },
        "drop_breakdown": {
            "source_to_quality_drop": source_to_quality_drop,
            "quality_to_strict_drop": quality_to_strict_drop,
            "source_to_strict_drop": source_to_strict_drop,
            "bottleneck": bottleneck,
        },
        "strict_selection": strict_selection,
        "strict_selection_details": selection_details[:50],  # Up to 50 entries for UI
        "strict_window_details": strict_window_details,
        "source_entry_ids": source_entry_ids[:100],
        "strict_entry_ids": strict_entry_ids[:100],
        "source_entry_ids_truncated": source_count > 100,
        "strict_entry_ids_truncated": strict_count > 100,
        "filters_used": {
            "grades": cfg.include_grades,
            "statuses": cfg.include_status,
            "labels": cfg.include_labels,
            "quality_floor_policy": cfg.quality_floor_policy,
            "quality_floor_value": cfg.quality_floor_value,
            "similarity_enabled": cfg.similarity_enabled,
            "min_strict_count": cfg.min_strict_count,
            "entry_windows": {
                feat: {"min": fcfg.get("min"), "max": fcfg.get("max")}
                for feat, fcfg in entry_filters.items()
            },
        },
        "annotation_stats": {
            "total_annotations": len(annotations),
            "matched_annotations": sum(1 for idx, row in df.iterrows() 
                                       if str(row.get(id_col, idx)) in ann_map),
        },
        "clamps_applied": clamps_applied,
        "quality_floor_applied": QUALITY_CLAMP_VALUE if clamps_applied.get("quality_entry_filter") else None,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "builder_version": "sniper_strategy_card_builder_v2.8",
    }
    
    # =========================================================================
    # Contract Validation v2.8
    # =========================================================================
    sqc = cfg.strict_contract
    
    # Pass selection_details to contract checker
    strict_selection_for_check = strict_selection.copy()
    strict_selection_for_check["strict_selection_details"] = selection_details
    
    contract_result = sqc.check_violations(strict_selection_for_check, strict_count)
    
    # Add contract info to provenance
    provenance["strict_contract"] = {
        "min_strict_count": sqc.min_strict_count,
        "max_distance_p50": sqc.max_distance_p50,
        "max_distance_p90": sqc.max_distance_p90,
        "max_auto_relax_ratio": sqc.max_auto_relax_ratio,
        "min_seed_count": sqc.min_seed_count,
        "enforce_mode": sqc.enforce_mode,
    }
    provenance["strict_contract_result"] = contract_result
    provenance["version"] = "v2.8"
    
    # Enforce BLOCK mode
    if sqc.enforce_mode == "BLOCK" and not contract_result["ok"]:
        violation_codes = [v["code"] for v in contract_result["violations"]]
        raise RuntimeError(
            f"Strict contract violated (BLOCK mode): {violation_codes}. "
            f"Suggestions: {contract_result['suggested_actions']}"
        )


    card: Dict[str, Any] = {
        "version": "sniper_strategy_card_v1",
        "symbol": symbol,
        "timeframe": timeframe,
        "source": {
            "insights_version": insights.get("version", "sniper_pattern_insights_v1"),
            "dataset_rows": len(df),
        },
        "labels": {
            "label_gain_column": insights.get("label_gain_column"),
            "gain_threshold_pct": insights.get("gain_threshold_pct"),
            "positive_rate": round(filters_obj["positive_rate"], 4),
            "positive_count": insights.get("positive_count"),
            "negative_count": insights.get("negative_count"),
        },
        "entry_filters": entry_filters,
        "feature_meta": filters_obj["feature_meta"],
        "pattern_rules_v1": {
            "enabled_by_default": True,
            "rules": filters_obj.get("pattern_rules", [])
        },
        "exit": {
            "tp_pct": None,
            "sl_pct": None,
            "max_horizon_bars": None,
        },
        "provenance": provenance,
        "meta": {
            "entries_total": source_count,
            "entries_selected": strict_count,
            "positive_rate": round(filters_obj["positive_rate"], 4),
        },
    }
    return card


def load_sniper_strategy_card(
    symbol: str,
    timeframe: str = "15m",
) -> Optional[Dict[str, Any]]:
    """Load existing sniper strategy card if exists."""
    base = Path("data/coin_profiles") / symbol.upper() / timeframe
    path = base / "sniper_strategy_card_v1.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Save Functions
# =============================================================================

def save_sniper_strategy_card_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
    cfg: Optional[SniperStrategyCardConfig] = None,
) -> Path:
    """Build and save sniper strategy card."""
    card = build_sniper_strategy_card_for_symbol_timeframe(symbol, timeframe, cfg)
    
    base = Path("data/coin_profiles") / symbol.upper() / timeframe
    base.mkdir(parents=True, exist_ok=True)

    path = base / "sniper_strategy_card_v1.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)

    num_filters = len(card.get("entry_filters", {}))
    print(f"[OK] Saved Sniper Strategy Card for {symbol} {timeframe}")
    print(f"     Path: {path}")
    print(f"     Filters: {num_filters}, Positive Rate: {card['labels']['positive_rate']:.1%}")
    
    return path


def save_sniper_strategy_cards_for_all_silver_15m_symbols() -> Dict[str, Path]:
    """Build strategy cards for all Silver 15m symbols."""
    results: Dict[str, Path] = {}
    
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        try:
            path = save_sniper_strategy_card_for_symbol_timeframe(sym, "15m")
            results[sym] = path
        except FileNotFoundError as e:
            print(f"[SKIP] {sym}: {e}")
        except Exception as e:
            print(f"[ERROR] {sym}: {e}")
    
    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    if not argv:
        print("Sniper Strategy Card Builder")
        print("=" * 40)
        print()
        print("Usage:")
        print("  python -m tezaver.sniper.sniper_strategy_card_builder SYMBOL [TIMEFRAME]")
        print("  python -m tezaver.sniper.sniper_strategy_card_builder all")
        print()
        print("Examples:")
        print("  python -m tezaver.sniper.sniper_strategy_card_builder BTCUSDT 15m")
        print("  python -m tezaver.sniper.sniper_strategy_card_builder all")
        sys.exit(0)

    if argv[0].lower() == "all":
        print("Building strategy cards for all Silver 15m symbols...")
        print()
        results = save_sniper_strategy_cards_for_all_silver_15m_symbols()
        print()
        print("Summary:")
        for sym, path in results.items():
            print(f"  ✓ {sym}: {path}")
        sys.exit(0)

    symbol = argv[0].upper()
    timeframe = argv[1] if len(argv) > 1 else "15m"
    
    try:
        path = save_sniper_strategy_card_for_symbol_timeframe(symbol, timeframe)
        print(f"✓ Done: {path}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
