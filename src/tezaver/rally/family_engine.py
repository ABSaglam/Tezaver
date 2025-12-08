import pandas as pd
import numpy as np
import json
import typing
from typing import List, Dict, Optional
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from tezaver.snapshots.snapshot_engine import get_symbol_pattern_dir
from tezaver.core.coin_cell_paths import get_project_root
from tezaver.wisdom.pattern_stats import get_coin_profile_dir
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def load_multi_tf_snapshots(symbol: str, base_timeframe: str) -> pd.DataFrame:
    """
    Loads multi-timeframe snapshots for a given symbol and base timeframe.
    """
    symbol_dir = get_symbol_pattern_dir(symbol)
    file_path = symbol_dir / f"snapshots_multi_{base_timeframe}.parquet"
    
    if not file_path.exists():
        logger.warning(f"Warning: Multi-TF snapshot file not found: {file_path}")
        return pd.DataFrame()
        
    try:
        return pd.read_parquet(file_path)
    except Exception as e:
        logger.error(f"Error loading multi-TF snapshots for {symbol} {base_timeframe}: {e}", exc_info=True)
        return pd.DataFrame()

def load_labeled_snapshots(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Loads labeled snapshots for a given symbol and timeframe.
    """
    symbol_dir = get_symbol_pattern_dir(symbol)
    file_path = symbol_dir / f"snapshots_labeled_{timeframe}.parquet"
    
    if not file_path.exists():
        logger.warning(f"Warning: Labeled snapshot file not found: {file_path}")
        return pd.DataFrame()
        
    try:
        return pd.read_parquet(file_path)
    except Exception as e:
        logger.error(f"Error loading labeled snapshots for {symbol} {timeframe}: {e}", exc_info=True)
        return pd.DataFrame()

def join_multi_with_labels(df_multi: pd.DataFrame, df_lab: pd.DataFrame) -> pd.DataFrame:
    """
    Joins multi-TF snapshots with labeled outcomes.
    """
    if df_multi.empty or df_lab.empty:
        return pd.DataFrame()
        
    # Ensure timestamp is datetime for merging
    if not pd.api.types.is_datetime64_any_dtype(df_multi["timestamp"]):
        df_multi["timestamp"] = pd.to_datetime(df_multi["timestamp"])
    if not pd.api.types.is_datetime64_any_dtype(df_lab["timestamp"]):
        df_lab["timestamp"] = pd.to_datetime(df_lab["timestamp"])

    # Merge on timestamp and trigger
    # We use left join to keep all multi snapshots, but we primarily care about those with labels
    # Actually, we only care about rallies, so inner join or left join + filter is fine.
    # The prompt says left join then filter.
    
    # Check if 'trigger' exists in both
    on_cols = ["timestamp"]
    if "trigger" in df_multi.columns and "trigger" in df_lab.columns:
        on_cols.append("trigger")
        
    df_merged = pd.merge(
        df_multi,
        df_lab[["timestamp", "trigger", "rally_label", "future_max_gain_pct", "future_max_loss_pct", "hit_5p", "hit_10p", "hit_20p"]],
        on=on_cols,
        how="left"
    )
    
    # Filter where rally_label is not "none" (and not null)
    df_merged = df_merged[df_merged["rally_label"].notna() & (df_merged["rally_label"] != "none")]
    
    return df_merged

def select_feature_columns(df: pd.DataFrame) -> List[str]:
    """
    Selects numeric feature columns for clustering.
    """
    features = []
    for col in df.columns:
        if col.startswith("tf_") and pd.api.types.is_numeric_dtype(df[col]):
            features.append(col)
    
    # Optionally include vol_rel from base TF if present (it might not have tf_ prefix if it's base)
    # But usually multi-tf snapshots prefix everything with tf_{timeframe}_...
    # If there are base columns without prefix, we can check for them.
    # For now, let's stick to "tf_" as per prompt, and maybe "vol_rel" if it exists explicitly.
    if "vol_rel" in df.columns and pd.api.types.is_numeric_dtype(df["vol_rel"]):
        features.append("vol_rel")
        
    return features

def determine_cluster_count(sample_count: int) -> int:
    """
    Determines the number of clusters based on sample count.
    """
    if sample_count < 40:
        return 1
    elif sample_count < 100:
        return 2
    elif sample_count < 300:
        return 3
    else:
        return 4

def cluster_rallies(df_rally: pd.DataFrame, n_clusters: int) -> pd.Series:
    """
    Clusters rally snapshots into families.
    Returns a Series of family IDs.
    """
    if df_rally.empty:
        return pd.Series(dtype=int)
        
    feature_cols = select_feature_columns(df_rally)
    if not feature_cols:
        print("Warning: No feature columns found for clustering.")
        return pd.Series([0] * len(df_rally), index=df_rally.index)
        
    X = df_rally[feature_cols].fillna(0) # Handle NaNs by filling with 0 or mean
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    
    return pd.Series(labels, index=df_rally.index, name="family_id")

def build_rally_families_for_symbol(symbol: str, base_timeframes: List[str]) -> None:
    """
    Builds rally families for a symbol across multiple base timeframes.
    """
    print(f"Building rally families for {symbol}...")
    
    for base_tf in base_timeframes:
        df_multi = load_multi_tf_snapshots(symbol, base_tf)
        df_lab = load_labeled_snapshots(symbol, base_tf)
        
        if df_multi.empty or df_lab.empty:
            continue
            
        df = join_multi_with_labels(df_multi, df_lab)
        
        if df.empty:
            print(f"  No rally snapshots found for {symbol} {base_tf}")
            continue
            
        # Initialize family_id column with -1 (or NaN)
        df["family_id"] = -1
        
        families_metadata = []
        
        for rally_class in ["rally_5p", "rally_10p", "rally_20p"]:
            df_rc = df[df["rally_label"] == rally_class].copy()
            
            if df_rc.empty:
                continue
                
            n_clusters = determine_cluster_count(len(df_rc))
            
            if n_clusters == 1:
                df_rc["family_id"] = 0
            else:
                family_ids = cluster_rallies(df_rc, n_clusters)
                df_rc["family_id"] = family_ids
            
            # Update the main df with these family IDs
            df.loc[df_rc.index, "family_id"] = df_rc["family_id"]
            
            # Compute stats for each family
            for fam_id in range(n_clusters):
                fam_rows = df_rc[df_rc["family_id"] == fam_id]
                if fam_rows.empty:
                    continue
                    
                sample_count = len(fam_rows)
                hit_5p_rate = fam_rows["hit_5p"].mean()
                hit_10p_rate = fam_rows["hit_10p"].mean()
                hit_20p_rate = fam_rows["hit_20p"].mean()
                
                trust_score = (0.4 * hit_5p_rate) + (0.3 * hit_10p_rate) + (0.3 * hit_20p_rate)
                
                fam_meta = {
                    "rally_class": rally_class,
                    "family_id": int(fam_id),
                    "sample_count": int(sample_count),
                    "trust_score": float(trust_score),
                    "avg_future_max_gain_pct": float(fam_rows["future_max_gain_pct"].mean()),
                    "avg_future_max_loss_pct": float(fam_rows["future_max_loss_pct"].mean()),
                    "hit_5p_rate": float(hit_5p_rate),
                    "hit_10p_rate": float(hit_10p_rate),
                    "hit_20p_rate": float(hit_20p_rate)
                }
                families_metadata.append(fam_meta)

        # Save enriched multi snapshot file (only rally rows have valid family_id)
        # We might want to save ALL rows, but only rally rows have family_id.
        # The prompt says "Save enriched multi snapshot file".
        # Let's save the dataframe that contains the merged info.
        # But wait, df only contains rally rows because of the filter in join_multi_with_labels.
        # If we want to persist this, we should probably save it as a separate "rallies" file or overwrite multi?
        # Prompt: "Save enriched multi snapshot file: snapshots_multi_{base_tf}_families.parquet"
        
        output_dir = get_symbol_pattern_dir(symbol)
        output_file = output_dir / f"snapshots_multi_{base_tf}_families.parquet"
        df.to_parquet(output_file)
        
        # Save JSON structure
        profile_dir = get_coin_profile_dir(symbol)
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        json_data = {
            "symbol": symbol,
            "base_timeframe": base_tf,
            "families": families_metadata
        }
        
        json_file = profile_dir / f"rally_families_{base_tf}.json"
        with open(json_file, "w") as f:
            json.dump(json_data, f, indent=2)
            
        print(f"  Saved rally families for {symbol} {base_tf} to {json_file}")

def bulk_build_rally_families(symbols: List[str], base_timeframes: List[str]) -> None:
    """
    Bulk builds rally families for multiple symbols.
    """
    for symbol in symbols:
        try:
            build_rally_families_for_symbol(symbol, base_timeframes)
        except Exception as e:
            print(f"Error building rally families for {symbol}: {e}")
            import traceback
            traceback.print_exc()
