"""
Sniper v4 - Selection Module
=============================

Deterministic trade selection based on filter window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class DatasetStats:
    """Statistics computed from dataset for window building."""
    rsi_min: float = 0
    rsi_max: float = 100
    rsi_p05: float = 20
    rsi_p95: float = 80
    volume_min: float = 0
    volume_max: float = 100
    volume_p05: float = 0.5
    volume_p95: float = 5.0
    atr_min: float = 0
    atr_max: float = 10
    atr_p05: float = 0.5
    atr_p95: float = 3.0
    quality_min: float = 0
    quality_max: float = 100
    quality_p05: float = 30
    quality_p95: float = 90


def compute_dataset_stats(df: pd.DataFrame) -> DatasetStats:
    """Compute statistics from dataset for window building."""
    stats = DatasetStats()
    
    # RSI
    rsi_col = None
    for c in ["rsi_15m", "feat_rsi_15m", "rsi"]:
        if c in df.columns:
            rsi_col = c
            break
    if rsi_col:
        s = df[rsi_col].dropna()
        if len(s) > 0:
            stats.rsi_min = float(s.min())
            stats.rsi_max = float(s.max())
            stats.rsi_p05 = float(np.percentile(s, 5))
            stats.rsi_p95 = float(np.percentile(s, 95))
    
    # Volume
    vol_col = None
    for c in ["volume_rel_15m", "feat_volume_rel_15m", "volume_ratio"]:
        if c in df.columns:
            vol_col = c
            break
    if vol_col:
        s = df[vol_col].dropna()
        if len(s) > 0:
            stats.volume_min = float(s.min())
            stats.volume_max = float(s.max())
            stats.volume_p05 = float(np.percentile(s, 5))
            stats.volume_p95 = float(np.percentile(s, 95))
    
    # ATR
    atr_col = None
    for c in ["atr_pct_15m", "feat_atr_pct_15m", "atr"]:
        if c in df.columns:
            atr_col = c
            break
    if atr_col:
        s = df[atr_col].dropna()
        if len(s) > 0:
            stats.atr_min = float(s.min())
            stats.atr_max = float(s.max())
            stats.atr_p05 = float(np.percentile(s, 5))
            stats.atr_p95 = float(np.percentile(s, 95))
    
    # Quality
    qual_col = None
    for c in ["quality_score", "feat_quality_score"]:
        if c in df.columns:
            qual_col = c
            break
    if qual_col:
        s = df[qual_col].dropna()
        if len(s) > 0:
            stats.quality_min = float(s.min())
            stats.quality_max = float(s.max())
            stats.quality_p05 = float(np.percentile(s, 5))
            stats.quality_p95 = float(np.percentile(s, 95))
    
    return stats


def build_window(
    tightness: int,
    toggles: Dict[str, bool],
    dataset_stats: DatasetStats,
    profile_window: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build effective filter window based on tightness.
    
    Args:
        tightness: 0-100 (0 = loose/dataset min-max, 100 = tight/profile or p05-p95)
        toggles: Filter enable flags (rsi, volume, atr, quality, ml)
        dataset_stats: Statistics from dataset
        profile_window: Optional profile-defined tight window
        
    Returns:
        Window dict with min/max for each enabled filter
    """
    t = tightness / 100.0
    
    window = {}
    
    # RSI
    if toggles.get("rsi", True):
        if profile_window and "rsi" in profile_window:
            tight_min = profile_window["rsi"].get("min", dataset_stats.rsi_p05)
            tight_max = profile_window["rsi"].get("max", dataset_stats.rsi_p95)
        else:
            tight_min = dataset_stats.rsi_p05
            tight_max = dataset_stats.rsi_p95
        
        window["rsi"] = {
            "min": dataset_stats.rsi_min + t * (tight_min - dataset_stats.rsi_min),
            "max": dataset_stats.rsi_max - t * (dataset_stats.rsi_max - tight_max),
            "enabled": True,
        }
    else:
        window["rsi"] = {"enabled": False}
    
    # Volume
    if toggles.get("volume", True):
        if profile_window and "volume" in profile_window:
            tight_min = profile_window["volume"].get("min", dataset_stats.volume_p05)
            tight_max = profile_window["volume"].get("max", dataset_stats.volume_p95)
        else:
            tight_min = dataset_stats.volume_p05
            tight_max = dataset_stats.volume_p95
        
        window["volume"] = {
            "min": dataset_stats.volume_min + t * (tight_min - dataset_stats.volume_min),
            "max": dataset_stats.volume_max - t * (dataset_stats.volume_max - tight_max),
            "enabled": True,
        }
    else:
        window["volume"] = {"enabled": False}
    
    # ATR
    if toggles.get("atr", True):
        if profile_window and "atr" in profile_window:
            tight_min = profile_window["atr"].get("min", dataset_stats.atr_p05)
            tight_max = profile_window["atr"].get("max", dataset_stats.atr_p95)
        else:
            tight_min = dataset_stats.atr_p05
            tight_max = dataset_stats.atr_p95
        
        window["atr"] = {
            "min": dataset_stats.atr_min + t * (tight_min - dataset_stats.atr_min),
            "max": dataset_stats.atr_max - t * (dataset_stats.atr_max - tight_max),
            "enabled": True,
        }
    else:
        window["atr"] = {"enabled": False}
    
    # Quality
    if toggles.get("quality", True):
        if profile_window and "quality" in profile_window:
            tight_min = profile_window["quality"].get("min", dataset_stats.quality_p05)
        else:
            tight_min = dataset_stats.quality_p05
        
        window["quality"] = {
            "min": dataset_stats.quality_min + t * (tight_min - dataset_stats.quality_min),
            "enabled": True,
        }
    else:
        window["quality"] = {"enabled": False}
    
    # ML (placeholder, always off for now)
    window["ml"] = {"enabled": toggles.get("ml", False)}
    
    return window


def select_trade_ids(
    df: pd.DataFrame,
    window: Dict[str, Any],
) -> List[str]:
    """
    Apply filters and return sorted unique trade_id list.
    
    Args:
        df: DataFrame with trade_id column and filter columns
        window: Filter window from build_window()
        
    Returns:
        Sorted unique list of trade_id strings
        
    Raises:
        RuntimeError: If duplicate trade_ids exist after filtering
    """
    if "trade_id" not in df.columns:
        raise ValueError("DataFrame must have 'trade_id' column")
    
    df_sel = df.copy()
    
    # Column mappings
    col_map = {
        "rsi": ["rsi_15m", "feat_rsi_15m", "rsi"],
        "volume": ["volume_rel_15m", "feat_volume_rel_15m", "volume_ratio"],
        "atr": ["atr_pct_15m", "feat_atr_pct_15m", "atr"],
        "quality": ["quality_score", "feat_quality_score"],
    }
    
    def find_col(candidates):
        for c in candidates:
            if c in df_sel.columns:
                return c
        return None
    
    # RSI filter
    rsi_cfg = window.get("rsi", {})
    if rsi_cfg.get("enabled", False):
        col = find_col(col_map["rsi"])
        if col:
            df_sel = df_sel[
                (df_sel[col] >= rsi_cfg["min"]) & (df_sel[col] <= rsi_cfg["max"])
            ]
    
    # Volume filter
    vol_cfg = window.get("volume", {})
    if vol_cfg.get("enabled", False):
        col = find_col(col_map["volume"])
        if col:
            df_sel = df_sel[
                (df_sel[col] >= vol_cfg["min"]) & (df_sel[col] <= vol_cfg["max"])
            ]
    
    # ATR filter
    atr_cfg = window.get("atr", {})
    if atr_cfg.get("enabled", False):
        col = find_col(col_map["atr"])
        if col:
            df_sel = df_sel[
                (df_sel[col] >= atr_cfg["min"]) & (df_sel[col] <= atr_cfg["max"])
            ]
    
    # Quality filter
    qual_cfg = window.get("quality", {})
    if qual_cfg.get("enabled", False):
        col = find_col(col_map["quality"])
        if col:
            df_sel = df_sel[df_sel[col] >= qual_cfg["min"]]
    
    # Extract trade_ids
    trade_ids = df_sel["trade_id"].tolist()
    unique_ids = sorted(set(trade_ids))
    
    # INVARIANT: No duplicates
    if len(unique_ids) != len(trade_ids):
        from collections import Counter
        c = Counter(trade_ids)
        dups = [k for k, v in c.items() if v > 1][:5]
        raise RuntimeError(
            f"[V4_DUPLICATE_IDS] total={len(trade_ids)} unique={len(unique_ids)} "
            f"dup_sample={dups}"
        )
    
    return unique_ids


# =============================================================================
# Card-Based Selection (CARD_STRICT / CARD_SOURCE modes)
# =============================================================================

def load_card_trade_ids(
    card_path,
    mode: str = "CARD_STRICT_IDS",
) -> List[str]:
    """
    Load trade IDs from sniper strategy card provenance.
    
    Args:
        card_path: Path to sniper_strategy_card_v1.json
        mode: "CARD_STRICT_IDS" or "CARD_SOURCE_IDS"
        
    Returns:
        Sorted unique list of trade_id strings from card
        
    Raises:
        FileNotFoundError: If card file not found
        KeyError: If required provenance fields missing
    """
    import json
    from pathlib import Path
    
    path = Path(card_path)
    if not path.exists():
        raise FileNotFoundError(f"Card not found: {path}")
    
    card = json.loads(path.read_text())
    prov = card.get("provenance", {})
    
    if mode == "CARD_STRICT_IDS":
        key = "strict_entry_ids"
    else:  # CARD_SOURCE_IDS
        key = "source_entry_ids"
    
    ids = prov.get(key, [])
    if not ids:
        # Fallback: try sample fields
        ids = prov.get(f"{key}_sample", [])
    
    return sorted(set(ids))


def load_card_contract_state(
    symbol: str,
    timeframe: str,
    card_path_hint=None,
) -> Dict[str, Any]:
    """
    Load contract state from sniper strategy card.
    
    Args:
        symbol: Coin symbol (e.g., "BTCUSDT")
        timeframe: Timeframe (e.g., "15m")
        card_path_hint: Optional explicit card path
        
    Returns:
        Dict with contract state or {"available": False} if not found
    """
    import json
    from pathlib import Path
    
    DATA_DIR = Path("data")
    
    # Find card path
    if card_path_hint:
        card_path = Path(card_path_hint)
    else:
        card_path = DATA_DIR / "coin_profiles" / symbol / timeframe / "sniper_strategy_card_v1.json"
        if not card_path.exists():
            card_path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_strategy_card_v1.json"
    
    if not card_path.exists():
        return {"available": False, "reason": "card_not_found"}
    
    try:
        card = json.loads(card_path.read_text())
        prov = card.get("provenance", {})
        
        contract_cfg = prov.get("strict_contract", {})
        contract_result = prov.get("strict_contract_result", {})
        strict_selection = prov.get("strict_selection", {})
        distance_stats = strict_selection.get("distance_stats", {})
        
        if not contract_result:
            return {"available": False, "reason": "no_contract_result"}
        
        return {
            "available": True,
            "enforce_mode": contract_cfg.get("enforce_mode", "WARN"),
            "ok": contract_result.get("ok", True),
            "violations": contract_result.get("violations", []),
            "suggested_actions": contract_result.get("suggested_actions", []),
            "auto_relax_ratio": contract_result.get("auto_relax_ratio", 0),
            "strict_count": prov.get("strict_count", 0),
            "seed_count": strict_selection.get("seed_count", 0),
            "distance_p50": distance_stats.get("p50"),
            "distance_p90": distance_stats.get("p90"),
            "card_path": str(card_path),
        }
        
    except Exception as e:
        return {"available": False, "reason": f"error: {e}"}


def select_by_mode(
    df: pd.DataFrame,
    mode: str,
    window: Dict[str, Any],
    card_path=None,
) -> List[str]:
    """
    Select trade IDs based on mode.
    
    Args:
        df: DataFrame with trade_id column
        mode: "ARENA_FILTERS", "CARD_STRICT_IDS", or "CARD_SOURCE_IDS"
        window: Filter window (only used for ARENA_FILTERS mode)
        card_path: Path to card file (required for CARD modes)
        
    Returns:
        Sorted unique list of trade_id strings
    """
    if mode == "ARENA_FILTERS":
        return select_trade_ids(df, window)
    
    elif mode in ("CARD_STRICT_IDS", "CARD_SOURCE_IDS"):
        if card_path is None:
            raise ValueError(f"card_path required for {mode}")
        
        card_ids = load_card_trade_ids(card_path, mode)
        
        # Intersect with dataset (card IDs must exist in df)
        df_ids = set(df["trade_id"].tolist())
        valid_ids = [id for id in card_ids if id in df_ids]
        
        return sorted(valid_ids)
    
    else:
        raise ValueError(f"Unknown selection mode: {mode}")
