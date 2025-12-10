"""
Tezaver ML Entry Feature Insights v1
=====================================

Compare feature distributions between good entries and others.
Output: Detailed statistics for top features identified by classifier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import json

import numpy as np
import pandas as pd


DATA_PATH = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
OUTPUT_PATH = Path("data/ai_insights/BTCUSDT/15m/entry_feature_insights_v1.json")


def _load_pattern_dataset() -> pd.DataFrame:
    """Load the pattern dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Pattern dataset not found at {DATA_PATH}")
    return pd.read_parquet(DATA_PATH)


def _safe_stats(s: pd.Series) -> Dict[str, float]:
    """Compute safe statistics for a series."""
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return {
            "count": 0,
            "mean": float("nan"),
            "std": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "p25": float("nan"),
            "p50": float("nan"),
            "p75": float("nan"),
        }

    return {
        "count": int(s.shape[0]),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if s.shape[0] > 1 else 0.0,
        "min": float(s.min()),
        "max": float(s.max()),
        "p25": float(s.quantile(0.25)),
        "p50": float(s.quantile(0.50)),
        "p75": float(s.quantile(0.75)),
    }


def _compare_feature_for_groups(
    df: pd.DataFrame,
    feature: str,
    label_col: str = "label_is_good_entry_v1",
) -> Dict[str, Any]:
    """
    Compare feature statistics between good (label=1) and other (label=0) groups.
    """
    if feature not in df.columns:
        return {
            "feature": feature,
            "available": False,
        }

    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found in dataset.")

    x = df[feature].replace([np.inf, -np.inf], np.nan)
    y = df[label_col].astype(int)

    good_mask = y == 1
    other_mask = y == 0

    good_stats = _safe_stats(x[good_mask])
    other_stats = _safe_stats(x[other_mask])

    # Compute differences
    diff = {}
    for key in ["mean", "p25", "p50", "p75"]:
        g_val = good_stats.get(key, float("nan"))
        o_val = other_stats.get(key, float("nan"))
        if pd.notna(g_val) and pd.notna(o_val):
            diff[f"{key}_diff"] = g_val - o_val
        else:
            diff[f"{key}_diff"] = float("nan")

    return {
        "feature": feature,
        "available": True,
        "label_col": label_col,
        "good_stats": good_stats,
        "other_stats": other_stats,
        "diff": diff,
    }


def build_entry_feature_insights_v1() -> Dict[str, Any]:
    """
    Build feature insights report for BTC 15m pattern dataset.
    Compares top features between good entries and others.
    """
    df = _load_pattern_dataset()

    label_col = "label_is_good_entry_v1"
    total = int(df.shape[0])
    pos = int(df[label_col].astype(int).sum()) if label_col in df.columns else 0

    # Top 3 features from classifier importance
    features: List[str] = [
        "feat_rsi_gap_1d",
        "feat_atr_pct_15m",
        "feat_rsi_1h",
    ]

    comparisons = []
    for f in features:
        comp = _compare_feature_for_groups(df, f, label_col=label_col)
        comparisons.append(comp)
        
        # Print summary
        if comp.get("available"):
            g = comp["good_stats"]
            o = comp["other_stats"]
            d = comp["diff"]
            print(f"\n=== {f} ===")
            print(f"Good entries (n={g['count']}): mean={g['mean']:.2f}, p50={g['p50']:.2f}, range=[{g['p25']:.2f}, {g['p75']:.2f}]")
            print(f"Other (n={o['count']}): mean={o['mean']:.2f}, p50={o['p50']:.2f}, range=[{o['p25']:.2f}, {o['p75']:.2f}]")
            print(f"Difference: mean_diff={d['mean_diff']:.2f}, p50_diff={d['p50_diff']:.2f}")

    report: Dict[str, Any] = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "label_col": label_col,
        "dataset": {
            "num_rows": total,
            "num_positive": pos,
            "num_negative": total - pos,
        },
        "features": comparisons,
    }

    return report


def save_entry_feature_insights_v1(path: Path = None) -> Path:
    """Save insights report to JSON."""
    if path is None:
        path = OUTPUT_PATH
        
    report = build_entry_feature_insights_v1()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return path


if __name__ == "__main__":
    print("=" * 60)
    print("BTC 15m Entry Feature Insights v1")
    print("=" * 60)
    
    path = save_entry_feature_insights_v1()
    print(f"\n[INFO] Entry feature insights v1 saved to: {path}")
