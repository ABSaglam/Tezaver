"""
Global Wisdom Module
Aggregates pattern statistics across all coins to identify universally reliable or treacherous patterns.
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any

from tezaver.core import coin_cell_paths
from tezaver.wisdom.pattern_stats import (
    get_coin_profile_dir,
    get_pattern_stats_file,
)


def get_global_wisdom_dir() -> Path:
    """Returns the global wisdom directory, creating it if needed."""
    root = coin_cell_paths.get_project_root()
    gw_dir = root / "data" / "global_wisdom"
    gw_dir.mkdir(parents=True, exist_ok=True)
    return gw_dir


def discover_symbols_from_profiles() -> List[str]:
    """Discovers symbols that have a profile directory."""
    root = coin_cell_paths.get_project_root()
    profile_root = root / "data" / "coin_profiles"
    
    if not profile_root.exists():
        return []
        
    symbols = []
    for item in profile_root.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            symbols.append(item.name)
            
    return sorted(symbols)


def build_global_pattern_wisdom(symbols: Optional[List[str]] = None) -> None:
    """
    Aggregates pattern_stats across all given symbols (or auto-discovers them),
    computes global trustworthy/betrayal lists and saves to data/global_wisdom/.
    """
    if symbols is None:
        symbols = discover_symbols_from_profiles()
        
    print(f"Building global wisdom for {len(symbols)} symbols...")
    
    frames = []
    
    for symbol in symbols:
        path = get_pattern_stats_file(symbol)
        if not path.exists():
            continue
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                
            if not json_data:
                continue
                
            df = pd.DataFrame(json_data)
            df["symbol"] = symbol
            frames.append(df)
        except Exception as e:
            print(f"Error loading stats for {symbol}: {e}")
            continue
            
    if not frames:
        print("No pattern stats found to aggregate.")
        return
        
    df_all = pd.concat(frames, ignore_index=True)
    
    # Ensure required columns exist
    required_cols = ["trigger", "sample_count", "hit_5p_rate", "hit_10p_rate", "hit_20p_rate", "trust_score"]
    for col in required_cols:
        if col not in df_all.columns:
            print(f"Missing column {col} in aggregated data.")
            return

    # Group by trigger
    # We aggregate stats to find patterns that work well GLOBALLY
    grouped = df_all.groupby("trigger")
    
    global_stats = []
    
    for trigger, group in grouped:
        total_samples = group["sample_count"].sum()
        
        # Weighted averages for hit rates
        # (rate * samples) / total_samples
        avg_hit_5p = (group["hit_5p_rate"] * group["sample_count"]).sum() / total_samples
        avg_hit_10p = (group["hit_10p_rate"] * group["sample_count"]).sum() / total_samples
        avg_hit_20p = (group["hit_20p_rate"] * group["sample_count"]).sum() / total_samples
        
        # Simple average for trust score (or could be weighted)
        avg_trust = group["trust_score"].mean()
        
        symbol_count = group["symbol"].nunique()
        # If timeframe column exists, count unique timeframes
        timeframe_count = group["timeframe"].nunique() if "timeframe" in group.columns else 0
        
        global_stats.append({
            "trigger": trigger,
            "global_sample_count": int(total_samples),
            "global_hit_5p_rate": float(avg_hit_5p),
            "global_hit_10p_rate": float(avg_hit_10p),
            "global_hit_20p_rate": float(avg_hit_20p),
            "global_trust_score": float(avg_trust),
            "symbol_count": int(symbol_count),
            "timeframe_count": int(timeframe_count)
        })
        
    stats_df_global = pd.DataFrame(global_stats)
    
    # Define thresholds for global wisdom
    MIN_SAMPLES = 50
    TRUST_TH = 0.6
    BETRAY_TH = 0.3
    
    # Trustworthy: High sample count, high hit rate
    trustworthy_global = stats_df_global[
        (stats_df_global["global_sample_count"] >= MIN_SAMPLES) &
        (stats_df_global["global_hit_5p_rate"] >= TRUST_TH)
    ].sort_values("global_trust_score", ascending=False)
    
    # Betrayal: High sample count, low hit rate
    betrayal_global = stats_df_global[
        (stats_df_global["global_sample_count"] >= MIN_SAMPLES) &
        (stats_df_global["global_hit_5p_rate"] <= BETRAY_TH)
    ].sort_values("global_trust_score", ascending=True)
    
    # Save results
    gw_dir = get_global_wisdom_dir()
    
    def save_df(path: Path, df: pd.DataFrame):
        records = df.to_dict(orient="records")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
            
    save_df(gw_dir / "global_pattern_stats.json", stats_df_global)
    save_df(gw_dir / "global_trustworthy_patterns.json", trustworthy_global)
    save_df(gw_dir / "global_betrayal_patterns.json", betrayal_global)
    
    print(f"Global wisdom saved to {gw_dir}")
    print(f"  - Global Stats: {len(stats_df_global)} patterns")
    print(f"  - Trustworthy: {len(trustworthy_global)} patterns")
    print(f"  - Betrayal: {len(betrayal_global)} patterns")


def build_global_regime_wisdom(symbols: Optional[List[str]] = None) -> None:
    """
    Aggregates regime_profile.json across all symbols to compute global regime insights.
    """
    if symbols is None:
        symbols = discover_symbols_from_profiles()
        
    print(f"Building global regime wisdom for {len(symbols)} symbols...")
    
    regime_data = []
    
    for symbol in symbols:
        profile_dir = get_coin_profile_dir(symbol)
        regime_file = profile_dir / "regime_profile.json"
        
        if not regime_file.exists():
            continue
            
        try:
            with open(regime_file, "r", encoding="utf-8") as f:
                profile = json.load(f)
                regime_data.append(profile)
        except Exception as e:
            print(f"Error loading regime profile for {symbol}: {e}")
            continue
    
    if not regime_data:
        print("No regime profiles found to aggregate.")
        return
    
    df = pd.DataFrame(regime_data)
    
    # Compute global metrics
    regime_counts = df["regime"].value_counts().to_dict()
    most_common_regime = df["regime"].mode()[0] if not df["regime"].empty else "unknown"
    
    global_metrics = {
        "total_symbols": len(df),
        "most_common_regime": most_common_regime,
        "regime_distribution": regime_counts,
        "avg_trendiness_score": float(df["trendiness_score"].mean()) if "trendiness_score" in df.columns else None,
        "avg_chop_score": float(df["chop_score"].mean()) if "chop_score" in df.columns else None,
        "avg_low_liquidity_score": float(df["low_liquidity_score"].mean()) if "low_liquidity_score" in df.columns else None,
        "avg_atr_pct": float(df["avg_atr_pct"].mean()) if "avg_atr_pct" in df.columns else None,
    }
    
    # Save to global wisdom directory
    gw_dir = get_global_wisdom_dir()
    output_path = gw_dir / "global_regime_wisdom.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(global_metrics, f, indent=2)
    
    print(f"Global regime wisdom saved to {output_path}")
    print(f"  - Most Common Regime: {most_common_regime}")
    print(f"  - Distribution: {regime_counts}")


def build_global_shock_wisdom(symbols: Optional[List[str]] = None) -> None:
    """
    Aggregates shock_profile.json across all symbols to compute global shock insights.
    """
    if symbols is None:
        symbols = discover_symbols_from_profiles()
        
    print(f"Building global shock wisdom for {len(symbols)} symbols...")
    
    shock_data = []
    
    for symbol in symbols:
        profile_dir = get_coin_profile_dir(symbol)
        shock_file = profile_dir / "shock_profile.json"
        
        if not shock_file.exists():
            continue
            
        try:
            with open(shock_file, "r", encoding="utf-8") as f:
                profile = json.load(f)
                shock_data.append(profile)
        except Exception as e:
            print(f"Error loading shock profile for {symbol}: {e}")
            continue
    
    if not shock_data:
        print("No shock profiles found to aggregate.")
        return
    
    df = pd.DataFrame(shock_data)
    
    # Compute global metrics
    total_shocks = int(df["total_shocks"].sum()) if "total_shocks" in df.columns else 0
    total_bars = int(df["total_bars"].sum()) if "total_bars" in df.columns else 0
    global_shock_freq = total_shocks / total_bars if total_bars > 0 else 0.0
    
    global_metrics = {
        "total_symbols": len(df),
        "total_shocks": total_shocks,
        "total_bars": total_bars,
        "global_shock_freq": float(global_shock_freq),
        "avg_shock_range_pct": float(df["avg_shock_range_pct"].mean()) if "avg_shock_range_pct" in df.columns else None,
    }
    
    # Create shock heatmap (coins with highest shock frequency)
    if "shock_freq" in df.columns:
        shock_heatmap = df[["symbol", "shock_freq"]].sort_values("shock_freq", ascending=False).head(10)
        global_metrics["shock_heatmap_top10"] = shock_heatmap.to_dict(orient="records")
    
    # Save to global wisdom directory
    gw_dir = get_global_wisdom_dir()
    output_path = gw_dir / "global_shock_wisdom.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(global_metrics, f, indent=2)
    
    print(f"Global shock wisdom saved to {output_path}")
    print(f"  - Global Shock Frequency: {global_shock_freq:.4f}")
    print(f"  - Total Shocks: {total_shocks}")

