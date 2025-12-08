"""
Pattern Stats Engine for Tezaver Mac.
Aggregates statistics from labeled snapshots to identify trustworthy and betrayal patterns.

Tezaver Philosophy:
- "Bu katman, desenlerin samimiyet sicilini tutar."
- "Trigger tek bir anlık sinyal değil, geçmiş performansını taşıyan bir karakterdir."
- "Bilgelik Paneli bu verileri kullanarak kullanıcıya hangi pattern'e ne kadar güvenileceğini gösterir."
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import sys

# Adjust path to allow imports if run directly or as module
from tezaver.core import coin_cell_paths
from tezaver.core.coin_cell_paths import get_coin_profile_dir
from tezaver.snapshots.snapshot_engine import (
    get_symbol_pattern_dir,
    get_snapshot_file,
    load_features, # Re-using M4 feature loader
)
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

# --- Path Helpers ---


def get_pattern_stats_file(symbol: str) -> Path:
    return get_coin_profile_dir(symbol) / "pattern_stats.json"

def get_trustworthy_patterns_file(symbol: str) -> Path:
    return get_coin_profile_dir(symbol) / "trustworthy_patterns.json"

def get_betrayal_patterns_file(symbol: str) -> Path:
    return get_coin_profile_dir(symbol) / "betrayal_patterns.json"

def get_volatility_signature_file(symbol: str) -> Path:
    return get_coin_profile_dir(symbol) / "volatility_signature.json"


# --- Data Loading ---

def load_labeled_snapshots(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Loads labeled snapshots for a symbol and timeframe.
    """
    symbol_pattern_dir = get_symbol_pattern_dir(symbol)
    labeled_file = symbol_pattern_dir / f"snapshots_labeled_{timeframe}.parquet"
    
    if not labeled_file.exists():
        raise FileNotFoundError(f"Labeled snapshots not found for {symbol} {timeframe}. Run M5 rally labeler first.")
        
    return pd.read_parquet(labeled_file)


# --- Stats Calculation ---

def compute_pattern_stats_for_symbol(symbol: str, timeframes: List[str]) -> pd.DataFrame:
    """
    Aggregates pattern statistics for a symbol across all timeframes.
    Returns a DataFrame with stats per trigger/timeframe.
    """
    stats_frames = []
    
    for tf in timeframes:
        try:
            df_lab = load_labeled_snapshots(symbol, tf)
        except FileNotFoundError:
            logger.warning(f"Warning: Labeled snapshots missing for {symbol} {tf}, skipping.")
            continue
            
        if df_lab.empty:
            continue
            
        required_cols = ["trigger", "future_max_gain_pct", "future_max_loss_pct", "hit_5p", "hit_10p", "hit_20p"]
        if not all(col in df_lab.columns for col in required_cols):
            logger.warning(f"Warning: Missing columns in labeled snapshots for {symbol} {tf}, skipping.")
            continue
            
        # Group by trigger
        grouped = df_lab.groupby("trigger")
        
        # Calculate stats
        stats = grouped.agg(
            sample_count=("trigger", "count"),
            avg_future_max_gain_pct=("future_max_gain_pct", "mean"),
            avg_future_max_loss_pct=("future_max_loss_pct", "mean"),
            hit_5p_rate=("hit_5p", "mean"),
            hit_10p_rate=("hit_10p", "mean"),
            hit_20p_rate=("hit_20p", "mean")
        ).reset_index()
        
        # Calculate rally label distribution
        # We can do this by iterating groups or using value_counts and reshaping
        # Iterating is simpler for readability here
        p_rally_5p_list = []
        p_rally_10p_list = []
        p_rally_20p_list = []
        
        for trigger in stats["trigger"]:
            group = grouped.get_group(trigger)
            total = len(group)
            if total > 0:
                p_rally_5p_list.append((group["rally_label"] == "rally_5p").mean())
                p_rally_10p_list.append((group["rally_label"] == "rally_10p").mean())
                p_rally_20p_list.append((group["rally_label"] == "rally_20p").mean())
            else:
                p_rally_5p_list.append(0.0)
                p_rally_10p_list.append(0.0)
                p_rally_20p_list.append(0.0)
                
        stats["p_rally_5p"] = p_rally_5p_list
        stats["p_rally_10p"] = p_rally_10p_list
        stats["p_rally_20p"] = p_rally_20p_list
        
        # Add metadata
        stats["symbol"] = symbol
        stats["timeframe"] = tf
        
        # Trust Score
        # Simple weighted average of hit rates
        stats["trust_score"] = (
            0.4 * stats["hit_5p_rate"] + 
            0.3 * stats["hit_10p_rate"] + 
            0.3 * stats["hit_20p_rate"]
        )
        
        stats_frames.append(stats)
        
    if not stats_frames:
        return pd.DataFrame()
        
    return pd.concat(stats_frames, ignore_index=True)


# --- Trust/Betrayal Filtering ---

# --- Configuration ---
from tezaver.core.config import (
    MIN_PATTERN_SAMPLES,
    TRUST_THRESHOLD,
    BETRAYAL_THRESHOLD,
)

def split_trustworthy_and_betrayal(stats_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Splits stats into trustworthy and betrayal patterns based on thresholds.

    Bu fonksiyon, tetik desenlerinin "güvenilir" mi yoksa "ihanetkâr" mı olduğuna karar verir.
    Eşikler hafifçe yumuşatıldı:

    - MIN_PATTERN_SAMPLES: Bir trigger'ın istatistiksel olarak anlamlı sayılması için gereken minimum örnek sayısı.
    - TRUST_THRESHOLD: Güvenilir sayılması için minimum hit_5p başarı oranı.
    - BETRAYAL_THRESHOLD: İhanetkar sayılması için maksimum hit_5p başarı oranı.

    Felsefe:
    - "Çok mükemmeliyetçi olmayalım; %50 civarı bile, piyasada gürültü düşünüldüğünde dikkate değer bir performanstır."
    - "Ama sürekli çuvallayan pattern'leri de affetmeyelim."
    """
    if stats_df.empty:
        return {"trustworthy": pd.DataFrame(), "betrayal": pd.DataFrame()}
        
    # Eşikler config.py'den geliyor

    # Trustworthy: Yeterince örnek var ve %5 rally yakalama oranı en az %50
    trust_mask = (stats_df["sample_count"] >= MIN_PATTERN_SAMPLES) & (stats_df["hit_5p_rate"] >= TRUST_THRESHOLD)
    trustworthy_df = stats_df[trust_mask].copy()
    trustworthy_df = trustworthy_df.sort_values("trust_score", ascending=False)
    
    # Betrayal: Yeterince örnek var ve %5 rally yakalama oranı %30 veya altında
    betray_mask = (stats_df["sample_count"] >= MIN_PATTERN_SAMPLES) & (stats_df["hit_5p_rate"] <= BETRAYAL_THRESHOLD)
    betrayal_df = stats_df[betray_mask].copy()
    # Sort betrayal by trust_score ascending (lowest trust first)
    betrayal_df = betrayal_df.sort_values("trust_score", ascending=True)
    
    return {"trustworthy": trustworthy_df, "betrayal": betrayal_df}


# --- Volatility Signature ---

def compute_volatility_signature(symbol: str, timeframes: List[str]) -> Dict[str, Any]:
    """
    Computes volatility signature for a coin.

    Yeni yaklaşım:
    - ATR'yi mutlak değer olarak değil, ATR% (ATR / close) olarak da hesaplarız.
    - Volatilite sınıfını ATR% üzerinden belirleriz:
        < 0.5%   -> Low
        0.5–1.5% -> Medium
        1.5–3%   -> High
        > 3%     -> Extreme

    Not:
    - avg_atr ve atr_std yine saklanır (ham ATR), ancak sınıflandırma ATR% üzerinden yapılır.
    """
    atr_values = []
    atr_pct_values = []
    vol_rel_values = []
    vol_spike_flags = []
    vol_dry_flags = []
    
    for tf in timeframes:
        try:
            # M4'ün load_features fonksiyonunu yeniden kullanıyoruz
            df_feat = load_features(symbol, tf)
        except FileNotFoundError:
            continue
            
        if df_feat.empty:
            continue
            
        # Ham ATR değerleri
        if "atr" in df_feat.columns:
            atr_values.extend(df_feat["atr"].dropna().tolist())
        
        # ATR% = ATR / close
        if "atr" in df_feat.columns and "close" in df_feat.columns:
            atr_series = df_feat["atr"].dropna()
            # ATR satırları ile aynı index'teki close değerlerini alalım
            close_series = df_feat.loc[atr_series.index, "close"].replace(0, pd.NA)
            atr_pct_series = (atr_series / close_series).dropna()
            atr_pct_values.extend(atr_pct_series.tolist())
            
        if "vol_rel" in df_feat.columns:
            vol_rel_values.extend(df_feat["vol_rel"].dropna().tolist())
            
        if "vol_spike" in df_feat.columns:
            vol_spike_flags.extend(df_feat["vol_spike"].dropna().tolist())
            
        if "vol_dry" in df_feat.columns:
            vol_dry_flags.extend(df_feat["vol_dry"].dropna().tolist())
            
    # Compute aggregates
    sig: Dict[str, Any] = {
        "avg_atr": None,
        "atr_std": None,
        "avg_atr_pct": None,      # ATR% ortalaması
        "atr_pct_std": None,      # ATR% std
        "avg_vol_rel": None,
        "vol_spike_freq": None,
        "vol_dry_freq": None,
        "volatility_class": "unknown",
    }
    
    # Ham ATR istatistikleri
    if atr_values:
        sig["avg_atr"] = float(np.mean(atr_values))
        sig["atr_std"] = float(np.std(atr_values))
    
    # ATR% istatistikleri ve volatilite sınıfı
    if atr_pct_values:
        avg_atr_pct = float(np.mean(atr_pct_values))
        atr_pct_std = float(np.std(atr_pct_values))
        sig["avg_atr_pct"] = avg_atr_pct
        sig["atr_pct_std"] = atr_pct_std
        
        # ATR% tipik olarak 0.01 -> %1, 0.03 -> %3 gibi değerler alır.
        # Eşikler:
        #   < 0.005  (0.5%)  -> Low
        #   < 0.015 (1.5%)   -> Medium
        #   < 0.03  (3%)     -> High
        #   >= 0.03          -> Extreme
        if avg_atr_pct < 0.005:
            sig["volatility_class"] = "Low"
        elif avg_atr_pct < 0.015:
            sig["volatility_class"] = "Medium"
        elif avg_atr_pct < 0.03:
            sig["volatility_class"] = "High"
        else:
            sig["volatility_class"] = "Extreme"
    
    # Hacim tarafı
    if vol_rel_values:
        sig["avg_vol_rel"] = float(np.mean(vol_rel_values))
        
    if vol_spike_flags:
        sig["vol_spike_freq"] = float(np.mean(vol_spike_flags))
        
    if vol_dry_flags:
        sig["vol_dry_freq"] = float(np.mean(vol_dry_flags))
        
    return sig



# --- Main Build Function ---

def build_wisdom_for_symbol(symbol: str, timeframes: List[str]) -> None:
    """
    Builds wisdom (stats, trust/betrayal lists, volatility sig) for a symbol.
    Saves to JSON files in data/coin_profiles/{SYMBOL}/.
    """
    # 1. Compute Stats
    stats_df = compute_pattern_stats_for_symbol(symbol, timeframes)
    
    # 2. Split Trust/Betrayal
    split = split_trustworthy_and_betrayal(stats_df)
    trustworthy_df = split["trustworthy"]
    betrayal_df = split["betrayal"]
    
    # 3. Volatility Signature
    volatility_signature = compute_volatility_signature(symbol, timeframes)
    
    # 4. Save
    profile_dir = get_coin_profile_dir(symbol)
    
    # Helper to save DF to JSON
    def save_df_json(df: pd.DataFrame, path: Path):
        # Convert to records
        records = df.to_dict(orient="records")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
            
    save_df_json(stats_df, get_pattern_stats_file(symbol))
    save_df_json(trustworthy_df, get_trustworthy_patterns_file(symbol))
    save_df_json(betrayal_df, get_betrayal_patterns_file(symbol))
    
    with open(get_volatility_signature_file(symbol), "w", encoding="utf-8") as f:
        json.dump(volatility_signature, f, indent=2)


def bulk_build_wisdom(symbols: List[str], timeframes: List[str]) -> None:
    """
    Builds wisdom for multiple coins.
    """
    for symbol in symbols:
        print(f"Building wisdom for {symbol}...")
        try:
            build_wisdom_for_symbol(symbol, timeframes)
        except Exception as e:
            print(f"Failed to build wisdom for {symbol}: {e}")
            continue
