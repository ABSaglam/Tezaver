"""
Rally Families Engine for Tezaver Mac (M9).
Groups multi-timeframe snapshots of real rallies into pattern families.

Tezaver Philosophy:
- "Büyük yükselişler aynı aileden gelir; biz o ailenin yüz hatlarını tanımak istiyoruz."
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from sklearn.cluster import KMeans

from tezaver.snapshots.multi_tf_snapshot_engine import (
    DEFAULT_BASE_TIMEFRAMES,
)
from tezaver.snapshots.snapshot_engine import (
    get_symbol_pattern_dir,
)
from tezaver.wisdom.pattern_stats import (
    get_coin_profile_dir,
    load_labeled_snapshots,
)

# --- Configuration ---

RALLY_LABELS = ["rally_5p", "rally_10p", "rally_20p"]

# Target cluster counts per rally label (upper bound, can shrink if few samples)
RALLY_CLUSTER_CONFIG: Dict[str, int] = {
    "rally_5p": 4,
    "rally_10p": 3,
    "rally_20p": 2,
}

# Minimum samples to even attempt clustering for a given label
MIN_SAMPLES_FOR_CLUSTERING = 50

# Desired minimum samples per cluster
MIN_SAMPLES_PER_CLUSTER = 15


# --- Path Helpers ---

def get_rally_families_file(symbol: str) -> Path:
    return get_coin_profile_dir(symbol) / "rally_families.json"

def get_rally_profile_file(symbol: str) -> Path:
    return get_coin_profile_dir(symbol) / "rally_profile.json"


# --- Data Load Helpers ---

def load_multi_tf_snapshots(symbol: str, base_timeframe: str) -> Optional[pd.DataFrame]:
    """
    Loads multi-timeframe snapshots for a symbol and base timeframe.
    File: library/patterns/{SYMBOL}/snapshots_multi_{base_tf}.parquet
    """
    symbol_dir = get_symbol_pattern_dir(symbol)
    file_path = symbol_dir / f"snapshots_multi_{base_timeframe}.parquet"
    if not file_path.exists():
        print(f"[M9] Multi-TF snapshots missing for {symbol} {base_timeframe}, skipping.")
        return None
    df = pd.read_parquet(file_path)
    if df.empty:
        print(f"[M9] Multi-TF snapshots empty for {symbol} {base_timeframe}.")
        return None
    # Ensure sorted
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def join_multi_with_labels(
    symbol: str,
    base_timeframe: str,
) -> Optional[pd.DataFrame]:
    """
    Joins labeled snapshots (M5) with multi-timeframe snapshots (M8)
    for a given symbol and base timeframe.

    Returns a DataFrame that includes:
    - rally outcome columns (future_max_gain_pct, hit_5p, hit_10p, hit_20p, rally_label)
    - multi-TF context columns (tf_* features)
    """
    # 1) Load labeled snapshots (single TF)
    try:
        df_lab = load_labeled_snapshots(symbol, base_timeframe)
    except FileNotFoundError:
        print(f"[M9] Labeled snapshots missing for {symbol} {base_timeframe}, skipping.")
        return None

    if df_lab.empty:
        print(f"[M9] Labeled snapshots empty for {symbol} {base_timeframe}.")
        return None

    # 2) Load multi-TF snapshots
    df_multi = load_multi_tf_snapshots(symbol, base_timeframe)
    if df_multi is None or df_multi.empty:
        return None

    # 3) Prepare subset of outcome columns from df_lab
    outcome_cols = [
        "symbol",
        "timeframe",
        "trigger",
        "timestamp",
        "datetime",
        "future_max_gain_pct",
        "future_max_loss_pct",
        "hit_5p",
        "hit_10p",
        "hit_20p",
        "rally_label",
    ]
    available_outcome_cols = [c for c in outcome_cols if c in df_lab.columns]

    df_lab_sub = df_lab[available_outcome_cols].copy()

    # 4) Join on key columns
    join_keys = [k for k in ["symbol", "timeframe", "trigger", "timestamp", "datetime"] if k in df_lab_sub.columns and k in df_multi.columns]

    df_full = pd.merge(
        df_multi,
        df_lab_sub,
        on=join_keys,
        how="left",
    )

    # Filter out rows without rally_label if column is missing
    if "rally_label" not in df_full.columns:
        print(f"[M9] rally_label column missing after join for {symbol} {base_timeframe}.")
        return None

    return df_full


# --- Feature Matrix Builder ---

def build_feature_matrix(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Builds a numeric feature matrix (X) from multi-timeframe snapshot DataFrame.

    Uses:
    - All columns starting with 'tf_' and numeric dtype.
    - Optionally base timeframe numeric columns like 'close', 'rsi' if present.

    Returns:
        {
            "X": np.ndarray of shape (n_samples, n_features),
            "feature_names": List[str]
        }
    or None if no usable features.
    """
    numeric_cols = []
    for col in df.columns:
        if col.startswith("tf_") and pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)

    # Optionally include base TF numeric fields
    for base_col in ["close", "rsi", "rsi_ema", "macd_hist", "atr"]:
        if base_col in df.columns and pd.api.types.is_numeric_dtype(df[base_col]):
            numeric_cols.append(base_col)

    numeric_cols = sorted(set(numeric_cols))

    if not numeric_cols:
        print("[M9] No numeric feature columns found for clustering.")
        return None

    X = df[numeric_cols].copy()

    # Fill NaN with column means, then any remaining NaN with 0
    X = X.fillna(X.mean())
    X = X.fillna(0.0)

    # Standardize per feature (z-score)
    X_values = X.values.astype(float)
    means = X_values.mean(axis=0)
    stds = X_values.std(axis=0)
    stds[stds == 0] = 1.0
    X_std = (X_values - means) / stds

    return {
        "X": X_std,
        "feature_names": numeric_cols,
    }


# --- Clustering ---

def cluster_rallies_for_label(
    df: pd.DataFrame,
    rally_label: str,
) -> Optional[pd.DataFrame]:
    """
    Clusters rows of df that correspond to a specific rally_label
    into rally families using KMeans.

    Adds a 'rally_family_id' column to the returned DataFrame.

    Returns:
        df_label_with_family or None if not enough samples.
    """
    df_label = df[df.get("rally_label") == rally_label].copy()
    if df_label.empty:
        # print(f"[M9] No rows for label {rally_label}.") # Too noisy
        return None

    n_samples = len(df_label)
    if n_samples < MIN_SAMPLES_FOR_CLUSTERING:
        # print(f"[M9] Not enough samples ({n_samples}) for clustering label {rally_label}.") # Too noisy
        return None

    feat = build_feature_matrix(df_label)
    if feat is None:
        return None

    X = feat["X"]

    # Determine cluster count based on sample size (M14 Logic)
    if n_samples < 40:
        k = 1
    elif n_samples < 100:
        k = 2
    elif n_samples < 300:
        k = 3
    else:
        k = 4
    
    # Override if k=1 (no clustering needed, just assign all to F0)
    if k == 1:
        # Just assign all to F0
        base_tf = None
        if "base_timeframe" in df_label.columns:
            base_tf = df_label["base_timeframe"].iloc[0]
        else:
            base_tf = df_label["timeframe"].iloc[0] if "timeframe" in df_label.columns else "unknown"
            
        df_label["rally_family_id"] = f"{base_tf}_{rally_label}_F0"
        return df_label

    if k < 1:
        print(f"[M9] Effective cluster count < 1 for {rally_label}, skipping.")
        return None

    model = KMeans(
        n_clusters=k,
        random_state=42,
        n_init=10,
    )
    cluster_ids = model.fit_predict(X)

    # Build family IDs like: "1h_rally_10p_F0" (including timeframe info from df)
    base_tf = None
    if "base_timeframe" in df_label.columns:
        base_tf = df_label["base_timeframe"].iloc[0]
    else:
        base_tf = df_label["timeframe"].iloc[0] if "timeframe" in df_label.columns else "unknown"

    family_ids = [
        f"{base_tf}_{rally_label}_F{cid}" for cid in cluster_ids
    ]
    df_label["rally_family_id"] = family_ids

    return df_label


# --- Stats & Profile ---

def compute_family_stats(
    df_families: pd.DataFrame,
    symbol: str,
) -> List[Dict[str, Any]]:
    """
    Aggregates stats per rally_family_id.

    Returns a list of dict records ready to be saved as JSON.
    """
    records: List[Dict[str, Any]] = []

    if df_families.empty:
        return records

    group = df_families.groupby("rally_family_id")

    for family_id, g in group:
        sample_count = len(g)

        avg_gain = float(g["future_max_gain_pct"].mean()) if "future_max_gain_pct" in g.columns else None
        avg_loss = float(g["future_max_loss_pct"].mean()) if "future_max_loss_pct" in g.columns else None

        hit_5p_rate = float(g["hit_5p"].mean()) if "hit_5p" in g.columns else None
        hit_10p_rate = float(g["hit_10p"].mean()) if "hit_10p" in g.columns else None
        hit_20p_rate = float(g["hit_20p"].mean()) if "hit_20p" in g.columns else None

        # Extract metadata from first row
        first = g.iloc[0]
        base_tf = first.get("base_timeframe", first.get("timeframe", "unknown"))
        rally_label = first.get("rally_label", "unknown")

        # Simple trust score (similar to pattern_stats)
        trust_score = None
        if hit_5p_rate is not None and hit_10p_rate is not None and hit_20p_rate is not None:
            trust_score = 0.4 * hit_5p_rate + 0.3 * hit_10p_rate + 0.3 * hit_20p_rate

        rec: Dict[str, Any] = {
            "symbol": symbol,
            "rally_family_id": family_id,
            "base_timeframe": base_tf,
            "rally_label": rally_label,
            "sample_count": sample_count,
            "avg_future_max_gain_pct": avg_gain,
            "avg_future_max_loss_pct": avg_loss,
            "hit_5p_rate": hit_5p_rate,
            "hit_10p_rate": hit_10p_rate,
            "hit_20p_rate": hit_20p_rate,
            "trust_score": float(trust_score) if trust_score is not None else None,
        }

        records.append(rec)

    return records


def build_rally_profile_from_families(
    symbol: str,
    family_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Builds a high-level rally profile JSON structure from family stats.
    Identifies 'preferred' and 'avoid' families based on trust_score and sample_count.
    """
    preferred: List[str] = []
    avoid: List[str] = []

    MIN_FAMILY_SAMPLES = 20
    TRUST_HIGH = 0.6
    TRUST_LOW = 0.3

    for rec in family_records:
        fid = rec.get("rally_family_id")
        trust = rec.get("trust_score")
        samples = rec.get("sample_count", 0)

        if fid is None or trust is None:
            continue

        if samples < MIN_FAMILY_SAMPLES:
            continue

        if trust >= TRUST_HIGH:
            preferred.append(fid)
        elif trust <= TRUST_LOW:
            avoid.append(fid)

    # Sort preferred by trust_score descending
    def get_trust(fid: str) -> float:
        for r in family_records:
            if r.get("rally_family_id") == fid:
                return float(r.get("trust_score") or 0.0)
        return 0.0

    preferred_sorted = sorted(preferred, key=get_trust, reverse=True)
    avoid_sorted = sorted(avoid, key=get_trust)  # lowest trust first

    profile: Dict[str, Any] = {
        "symbol": symbol,
        "preferred_families": preferred_sorted,
        "avoid_families": avoid_sorted,
        "total_families": len(family_records),
    }

    return profile


# --- Main Logic ---

def build_rally_families_for_symbol(
    symbol: str,
    base_timeframes: List[str],
) -> None:
    """
    Builds rally families and rally profile for a single symbol across given base timeframes.

    Steps:
    - For each base timeframe:
        - Join multi-TF snapshots with labeled snapshots.
        - For each rally label (rally_5p / rally_10p / rally_20p):
            - Cluster into families if enough samples.
    - Aggregate family stats.
    - Save rally_families.json and rally_profile.json.
    """
    all_family_rows: List[pd.DataFrame] = []

    for base_tf in base_timeframes:
        print(f"[M9] Processing {symbol} {base_tf} for rally families...")
        df_full = join_multi_with_labels(symbol, base_tf)
        if df_full is None or df_full.empty:
            continue

        for label in RALLY_LABELS:
            df_label_with_family = cluster_rallies_for_label(df_full, label)
            if df_label_with_family is not None and not df_label_with_family.empty:
                all_family_rows.append(df_label_with_family)

    if not all_family_rows:
        print(f"[M9] No rally families built for {symbol}.")
        # Still create empty files for consistency
        profile_dir = get_coin_profile_dir(symbol)
        profile_dir.mkdir(parents=True, exist_ok=True)

        with open(get_rally_families_file(symbol), "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

        with open(get_rally_profile_file(symbol), "w", encoding="utf-8") as f:
            json.dump({"symbol": symbol, "preferred_families": [], "avoid_families": [], "total_families": 0}, f, indent=2)
        return

    df_all = pd.concat(all_family_rows, ignore_index=True)

    # Compute stats
    family_records = compute_family_stats(df_all, symbol)

    # Save family records
    profile_dir = get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with open(get_rally_families_file(symbol), "w", encoding="utf-8") as f:
        json.dump(family_records, f, indent=2)

    # Build profile
    profile = build_rally_profile_from_families(symbol, family_records)
    with open(get_rally_profile_file(symbol), "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def bulk_build_rally_families(
    symbols: List[str],
    base_timeframes: Optional[List[str]] = None,
) -> None:
    """
    Builds rally families and profiles for multiple symbols.
    """
    if base_timeframes is None:
        base_timeframes = DEFAULT_BASE_TIMEFRAMES

    for symbol in symbols:
        print(f"[M9] Building rally families for {symbol}...")
        try:
            build_rally_families_for_symbol(symbol, base_timeframes)
        except Exception as e:
            print(f"[M9] Failed to build rally families for {symbol}: {e}")
            continue
