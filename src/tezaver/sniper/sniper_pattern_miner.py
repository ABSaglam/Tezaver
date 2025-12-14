"""
Sniper Pattern Miner - ML Analysis for Sniper Entry Patterns
=============================================================

Extracts common patterns from sniper entries using ML:
- Which features correlate with good sniper entries?
- RSI / ATR / volume / MACD - which ranges have higher "good rate"?

Output: data/ai_insights/{symbol}/{timeframe}/sniper_pattern_insights_v1.json
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import json
import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# =============================================================================
# Constants
# =============================================================================

META_COLS = {
    "symbol",
    "timeframe",
    "event_id",
    "entry_ts",
    "entry_bar_index",
    "entry_bar_offset",
    "sniper_note",
    "sniper_created_at",
}

LABEL_COL_CANDIDATES_GAIN = [
    "future_max_gain_pct",
    "label_future_max_gain_pct",
    "gain_pct",
]

LABEL_COL_CANDIDATES_DD = [
    "future_min_drawdown_pct",
    "label_future_min_drawdown_pct",
    "pre_peak_dd_pct",
]


# =============================================================================
# Config
# =============================================================================

@dataclass
class SniperMLConfig:
    """Configuration for sniper pattern mining."""
    gain_threshold_pct: Optional[float] = None  # Auto p75 if None
    min_samples_for_model: int = 10
    n_estimators: int = 200
    random_state: int = 42
    max_features: str = "sqrt"
    top_k_features: int = 10
    n_bins: int = 5  # quantile bins


# =============================================================================
# Helpers
# =============================================================================

def _load_sniper_entries(symbol: str, timeframe: str = "15m") -> pd.DataFrame:
    """Load sniper entries dataset."""
    base = Path("data/ai_datasets") / symbol.upper() / timeframe
    path = base / "sniper_entries_v1.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Sniper entries dataset not found at: {path}")
    return pd.read_parquet(path)


def _find_label_columns(df: pd.DataFrame) -> Tuple[str, Optional[str]]:
    """Find gain and drawdown label columns."""
    gain_col = None
    for c in LABEL_COL_CANDIDATES_GAIN:
        if c in df.columns:
            gain_col = c
            break
    if gain_col is None:
        raise ValueError(
            f"No gain label column found. Looked for: {LABEL_COL_CANDIDATES_GAIN}"
        )

    dd_col = None
    for c in LABEL_COL_CANDIDATES_DD:
        if c in df.columns:
            dd_col = c
            break
    
    return gain_col, dd_col


def _build_label_good_entry(
    df: pd.DataFrame,
    gain_col: str,
    cfg: SniperMLConfig,
) -> Tuple[pd.DataFrame, float]:
    """Build binary label for 'good entry' based on gain threshold."""
    df = df.copy()
    
    # Clean infinities
    valid = df[gain_col].replace([np.inf, -np.inf], np.nan).dropna()
    if valid.empty:
        raise ValueError(f"All values in {gain_col} are NaN/inf; cannot build label.")

    # Threshold
    if cfg.gain_threshold_pct is None:
        thr = float(valid.quantile(0.75))
    else:
        thr = float(cfg.gain_threshold_pct)

    df["label_good_entry"] = (df[gain_col] >= thr).astype(int)
    return df, thr


def _select_feature_columns(df: pd.DataFrame) -> List[str]:
    """Select numeric feature columns for ML."""
    cols: List[str] = []
    for c in df.columns:
        if c in META_COLS:
            continue
        if c.startswith("future_"):
            continue
        if c.startswith("label_"):
            continue
        if c in ("is_silver",):
            continue

        if np.issubdtype(df[c].dtype, np.number):
            if df[c].nunique(dropna=True) > 1:
                cols.append(c)

    return cols


def _train_model_and_importances(
    df: pd.DataFrame,
    feature_cols: List[str],
    cfg: SniperMLConfig,
) -> Tuple[Any, Dict[str, float]]:
    """Train RandomForest and get feature importances."""
    if not SKLEARN_AVAILABLE:
        return None, {}
    
    # Need at least 2 classes
    if df["label_good_entry"].nunique() < 2 or len(df) < cfg.min_samples_for_model:
        return None, {}

    X = df[feature_cols].astype(float).fillna(0)
    y = df["label_good_entry"].astype(int)

    try:
        test_size = min(0.3, max(0.2, 3 / len(df)))
        X_train, _, y_train, _ = train_test_split(
            X, y, test_size=test_size, random_state=cfg.random_state, stratify=y
        )
    except ValueError:
        X_train, y_train = X, y

    model = RandomForestClassifier(
        n_estimators=cfg.n_estimators,
        random_state=cfg.random_state,
        class_weight="balanced",
        max_features=cfg.max_features,
    )
    model.fit(X_train, y_train)

    importances = model.feature_importances_
    feature_importance_map = {
        f: float(w) for f, w in zip(feature_cols, importances)
    }

    return model, feature_importance_map


def _compute_feature_bins(
    df: pd.DataFrame,
    feature_cols: List[str],
    cfg: SniperMLConfig,
) -> Dict[str, Any]:
    """Compute good_rate per quantile bin for each feature."""
    result: Dict[str, Any] = {}
    
    for feat in feature_cols:
        series = df[feat].replace([np.inf, -np.inf], np.nan).dropna()
        if series.empty:
            continue

        try:
            qs = np.linspace(0.0, 1.0, cfg.n_bins + 1)
            bins = series.quantile(qs).values
            
            categories = pd.cut(
                df[feat],
                bins=np.unique(bins),
                include_lowest=True,
                duplicates="drop",
            )
        except Exception:
            continue

        grouped = df.groupby(categories, observed=True)["label_good_entry"]
        bin_stats = []
        
        for cat, grp in grouped:
            if cat is pd.NA or cat is None:
                continue
            if grp.empty:
                continue
            
            good_rate = float(grp.mean())
            count = int(len(grp))
            bin_stats.append({
                "bin": str(cat),
                "count": count,
                "good_rate": round(good_rate, 4),
            })

        if bin_stats:
            result[feat] = {
                "bins": bin_stats,
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
            }

    return result


# =============================================================================
# Main Miner Function
# =============================================================================

def run_sniper_pattern_miner_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
    cfg: Optional[SniperMLConfig] = None,
) -> Dict[str, Any]:
    """
    Run pattern mining on sniper entries dataset.
    
    Returns:
        Dictionary with insights including feature importances and bin stats.
    """
    if cfg is None:
        cfg = SniperMLConfig()

    symbol = symbol.upper()
    df = _load_sniper_entries(symbol, timeframe)
    gain_col, dd_col = _find_label_columns(df)

    df_labeled, thr = _build_label_good_entry(df, gain_col, cfg)
    feature_cols = _select_feature_columns(df_labeled)

    model, fi_map = _train_model_and_importances(df_labeled, feature_cols, cfg)

    # Sort features by importance
    sorted_feats = sorted(fi_map.items(), key=lambda kv: kv[1], reverse=True)
    top_feats = [f for f, _ in sorted_feats[:cfg.top_k_features]]

    # Compute bin stats for top features
    feature_bins = _compute_feature_bins(df_labeled, top_feats, cfg)

    # Basic statistics
    total = int(len(df_labeled))
    pos = int(df_labeled["label_good_entry"].sum())
    neg = total - pos
    positive_rate = round(float(pos / total), 4) if total > 0 else 0.0

    summary: Dict[str, Any] = {
        "version": "sniper_pattern_insights_v1",
        "symbol": symbol,
        "timeframe": timeframe,
        "num_entries": total,
        "label_gain_column": gain_col,
        "gain_threshold_pct": round(thr, 4),
        "positive_count": pos,
        "negative_count": neg,
        "positive_rate": positive_rate,
        "config": asdict(cfg),
        "model_trained": model is not None,
        "feature_importances": [
            {"feature": f, "importance": round(float(w), 4)} for f, w in sorted_feats
        ],
        "top_features": top_feats,
        "feature_bins": feature_bins,
    }

    return summary


# =============================================================================
# Save Functions
# =============================================================================

def save_sniper_pattern_insights_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
    cfg: Optional[SniperMLConfig] = None,
) -> Path:
    """Run pattern miner and save insights to JSON."""
    summary = run_sniper_pattern_miner_for_symbol_timeframe(symbol, timeframe, cfg)

    base_dir = Path("data/ai_insights") / symbol.upper() / timeframe
    base_dir.mkdir(parents=True, exist_ok=True)

    path = base_dir / "sniper_pattern_insights_v1.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"[OK] Saved sniper pattern insights for {symbol} {timeframe}")
    print(f"     Path: {path}")
    print(f"     Entries: {summary['num_entries']}, Positive Rate: {summary['positive_rate']:.1%}")
    print(f"     Top Features: {', '.join(summary['top_features'][:5])}")
    
    return path


def save_sniper_pattern_insights_for_all_silver_15m_symbols() -> Dict[str, Path]:
    """Run pattern miner for all Silver 15m symbols."""
    results: Dict[str, Path] = {}
    
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        try:
            path = save_sniper_pattern_insights_for_symbol_timeframe(sym, "15m")
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
        print("Sniper Pattern Miner")
        print("=" * 40)
        print()
        print("Usage:")
        print("  python -m tezaver.sniper.sniper_pattern_miner SYMBOL [TIMEFRAME]")
        print("  python -m tezaver.sniper.sniper_pattern_miner all")
        print()
        print("Examples:")
        print("  python -m tezaver.sniper.sniper_pattern_miner BTCUSDT 15m")
        print("  python -m tezaver.sniper.sniper_pattern_miner all")
        sys.exit(0)

    if argv[0].lower() == "all":
        print("Running pattern miner for all Silver 15m symbols...")
        print()
        results = save_sniper_pattern_insights_for_all_silver_15m_symbols()
        print()
        print("Summary:")
        for sym, path in results.items():
            print(f"  ✓ {sym}: {path}")
        sys.exit(0)

    symbol = argv[0].upper()
    timeframe = argv[1] if len(argv) > 1 else "15m"
    
    try:
        path = save_sniper_pattern_insights_for_symbol_timeframe(symbol, timeframe)
        print(f"✓ Done: {path}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
