"""
Trend & Levels Engine for Tezaver Mac.

Felsefe:
- "Fiyatın gittiği yer kadar, dönmeye alıştığı yer de önemlidir."
- "Destek/direnç, piyasanın geçmişte 'buraya kadar', 'buradan dönerim' dediği izlerdir."
- "Çıkış (TP) sanatı, bu izleri ciddiye almakla başlar."
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys
import json

from tezaver.core import coin_cell_paths
from tezaver.wisdom.pattern_stats import get_coin_profile_dir

# --- Configuration ---

# Hangi TF'ler için seviyeler üretilecek?
DEFAULT_LEVEL_TIMEFRAMES = ["1h", "4h", "1d"]

# Pivot penceresi (kaç mum sağ/sol)
PIVOT_WINDOW = 2  # 2 sol, 2 sağ = toplam 5 mumluk lokal tepe/dip

# Zone birleştirme toleransı (yüzde)
ZONE_MERGE_TOLERANCE = 0.003  # %0.3 civarı

# Minimum dokunma sayısı
MIN_TOUCH_COUNT = 2


# --- Pivot Detection ---

def detect_pivots(df: pd.DataFrame, window: int = PIVOT_WINDOW) -> pd.DataFrame:
    """
    high/low serilerinden pivot high / pivot low noktalarını işaretler.
    df: en az 'high', 'low', 'close', 'timestamp' içermeli.
    Çıktı: df'e 'pivot_high' ve 'pivot_low' (0/1) sütunları ekler.
    """
    df = df.copy()
    
    # Initialize columns
    df["pivot_high"] = 0
    df["pivot_low"] = 0
    
    # We need a rolling window check, but pandas rolling is for past data.
    # For pivots, we need future data too (i+1, i+2).
    # Efficient way: shift and compare.
    
    # Pivot High: high[i] > neighbors
    is_high = pd.Series(True, index=df.index)
    for i in range(1, window + 1):
        is_high &= (df["high"] > df["high"].shift(i))
        is_high &= (df["high"] >= df["high"].shift(-i))
        
    # Pivot Low: low[i] < neighbors
    is_low = pd.Series(True, index=df.index)
    for i in range(1, window + 1):
        is_low &= (df["low"] < df["low"].shift(i))
        is_low &= (df["low"] <= df["low"].shift(-i))
        
    df.loc[is_high, "pivot_high"] = 1
    df.loc[is_low, "pivot_low"] = 1
    
    return df


# --- Zone Building ---

def build_level_zones_from_pivots(
    df: pd.DataFrame,
    tf: str
) -> List[Dict[str, Any]]:
    """
    Pivotlardan level zone listesi oluşturur.
    Çıktı: her biri dict olan bir liste (JSON'a yazılabilir).
    """
    zones: List[Dict[str, Any]] = []
    
    # Extract pivot points
    # We use 'close' price for level reference as per philosophy, 
    # but could use high/low if strict wicks are preferred.
    # Using close makes it more robust against wick noise.
    
    pivots_high = df[df["pivot_high"] == 1][["timestamp", "close"]].copy()
    pivots_low = df[df["pivot_low"] == 1][["timestamp", "close"]].copy()
    
    # Combine into a single stream of events, tagging type
    pivots_high["type"] = "resistance"
    pivots_low["type"] = "support"
    
    all_pivots = pd.concat([pivots_high, pivots_low]).sort_values("timestamp")
    
    if all_pivots.empty:
        return []
        
    # Process pivots one by one
    for _, row in all_pivots.iterrows():
        price = float(row["close"])
        ts = int(row["timestamp"])
        ptype = row["type"]
        
        # Try to find an existing zone to merge into
        merged = False
        for zone in zones:
            # Check price proximity
            zone_price = zone["level_price"]
            diff_pct = abs(price - zone_price) / zone_price
            
            if diff_pct <= ZONE_MERGE_TOLERANCE:
                # Merge!
                zone["touch_count"] += 1
                zone["last_seen_ts"] = ts
                
                # Update price (weighted average could be better, but simple average of current level + new price is okay for drift)
                # Let's do a simple moving average update to allow level to evolve
                n = zone["touch_count"]
                zone["level_price"] = (zone_price * (n - 1) + price) / n
                
                # If type matches, reinforce. If opposite, it becomes a flip zone (S/R flip).
                # For now, we keep the original type or maybe mark as "flip"?
                # Let's keep simple: if it acts as both, it's a strong level.
                if zone["type"] != ptype:
                    zone["is_flip"] = True
                
                merged = True
                break
        
        if not merged:
            # Create new zone
            new_zone = {
                "timeframe": tf,
                "type": ptype,
                "level_price": price,
                "touch_count": 1,
                "first_seen_ts": ts,
                "last_seen_ts": ts,
                "is_flip": False
            }
            zones.append(new_zone)
            
    # Post-processing: Calculate scores and filter
    final_zones = []
    
    if not zones:
        return []
        
    max_touches = max(z["touch_count"] for z in zones)
    current_ts = int(df["timestamp"].iloc[-1])
    
    for zone in zones:
        if zone["touch_count"] < MIN_TOUCH_COUNT:
            continue
            
        # Strength Score Calculation
        # 1. Normalized touches
        norm_touch = zone["touch_count"] / max_touches if max_touches > 0 else 0
        
        # 2. Recency (how close is last touch to now?)
        # Let's say if last touch is within last 100 bars, it's very relevant.
        # If it's very old, score drops.
        # Simple linear decay isn't perfect but works.
        # Let's use a simpler heuristic: 
        # If last_seen is recent (e.g. within last 20% of history duration), high score.
        
        # Alternative: just use touch count and maybe a boost for recent touches.
        # Let's stick to the plan: 0.6 * touch + 0.4 * recency
        
        # Recency score: 1.0 if last touch is NOW, 0.0 if last touch is at start of history
        total_duration = current_ts - df["timestamp"].iloc[0]
        if total_duration <= 0:
            recency = 1.0
        else:
            recency = (zone["last_seen_ts"] - df["timestamp"].iloc[0]) / total_duration
            
        strength = 0.6 * norm_touch + 0.4 * recency
        
        # Boost for flip zones
        if zone.get("is_flip"):
            strength *= 1.2
            
        zone["strength_score"] = round(min(1.0, strength), 4)
        zone["level_price"] = round(zone["level_price"], 4)
        
        final_zones.append(zone)
        
    # Sort by price for easier reading
    final_zones.sort(key=lambda x: x["level_price"])
    
    return final_zones


# --- Orchestration ---

def build_levels_for_symbol_timeframe(symbol: str, timeframe: str) -> List[Dict[str, Any]]:
    """
    Belirli bir coin + timeframe için:
    - history_{tf}.parquet yükler
    - pivotları hesaplar
    - zone'ları çıkarır
    - JSON olarak kaydeder
    """
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    if not history_file.exists():
        print(f"History not found for {symbol} {timeframe}, skipping levels.")
        return []
        
    try:
        df = pd.read_parquet(history_file)
    except Exception as e:
        print(f"Error reading history for {symbol} {timeframe}: {e}")
        return []
        
    if df.empty:
        return []
        
    # Detect pivots
    df_pivots = detect_pivots(df)
    
    # Build zones
    levels = build_level_zones_from_pivots(df_pivots, timeframe)
    
    # Save to profile
    profile_dir = get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = profile_dir / f"levels_{timeframe}.json"
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(levels, f, indent=2)
        
    return levels


def bulk_build_levels(
    symbols: List[str],
    timeframes: List[str] = DEFAULT_LEVEL_TIMEFRAMES
) -> None:
    for symbol in symbols:
        for tf in timeframes:
            try:
                print(f"Building levels for {symbol} {tf}...")
                levels = build_levels_for_symbol_timeframe(symbol, tf)
                print(f"  -> Found {len(levels)} zones.")
            except Exception as e:
                print(f"Failed to build levels for {symbol} {tf}: {e}")
                continue
