
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
from typing import Dict, List, Optional
import streamlit as st

class ArchetypeService:
    """
    Service to scan and classify historical rallies into Archetypes.
    """
    
    def __init__(self, coin_cells_path: str = "/Users/alisaglam/TezaverMac/coin_cells"):
        self.root_dir = Path(coin_cells_path)

    def get_available_coins(self) -> List[str]:
        """List coins available in coin_cells."""
        if not self.root_dir.exists():
            return []
        coins = [d.name for d in self.root_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        return sorted(coins)

    def get_available_timeframes(self, symbol: str) -> List[str]:
        """List available timeframes for a coin."""
        data_dir = self.root_dir / symbol / "data"
        if not data_dir.exists():
            return []
        
        # Scan features_*.parquet
        files = list(data_dir.glob("features_*.parquet"))
        tfs = []
        for f in files:
            # features_15m.parquet -> 15m
            name = f.stem
            if "_" in name:
                tf = name.split("_")[1]
                tfs.append(tf)
        
        # Sort logic: 15m, 1h, 4h, 1d, 1w
        order = {"15m": 1, "1h": 2, "4h": 3, "1d": 4, "1w": 5}
        tfs.sort(key=lambda x: order.get(x, 99))
        return tfs

    @st.cache_data(ttl=300)
    def scan_coin_archetypes(_self, symbol: str, timeframe: str = "15m") -> Dict[str, Dict[str, List[Dict]]]:
        """
        Scans history for rallies (>5%) and classifies them by Archetype and Tier.
        Returns: {
            "archetypes": { "GRIND": [], ... },
            "tiers": { "DIAMOND": [], "GOLD": [], "SILVER": [], "BRONZE": [] }
        }
        """
        feat_path = _self.root_dir / symbol / "data" / f"features_{timeframe}.parquet"
        
        # Initialize buckets
        archetypes = {
            "GRIND": [], "GUILLOTINE": [], "SUPERNOVA": [], 
            "PHOENIX": [], "NINJA": [], "SURFER": [], "OTHER": []
        }
        tiers = {
            "DIAMOND 💎": [], # >= 30%
            "GOLD 🥇": [],    # 20-30%
            "SILVER 🥈": [],  # 10-20%
            "BRONZE 🥉": []   # 5-10%
        }
        
        if not feat_path.exists():
            return {"archetypes": archetypes, "tiers": tiers}
            
        try:
            df = pd.read_parquet(feat_path)
            
            if 'timestamp' in df.columns: 
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Map columns logic (simplified for brevity, assuming standard or mapped previously)
            col_map = {
                f'rsi_{timeframe}': 'rsi',
                f'volume_rel_{timeframe}': 'volume_rel',
                'rsi_15m': 'rsi', 'volume_rel_15m': 'volume_rel',
                'vol_rel': 'volume_rel'
            }
            for old, new in col_map.items():
                if old in df.columns and new not in df.columns: df[new] = df[old]

            if 'rsi' not in df.columns or 'volume_rel' not in df.columns:
                 # Last fallback
                 if 'rsi' not in df.columns and 'rsi_15m' in df.columns: df['rsi'] = df['rsi_15m']
                 if 'volume_rel' not in df.columns and 'vol_rel' in df.columns: df['volume_rel'] = df['vol_rel']
            
            if 'rsi' not in df.columns or 'volume_rel' not in df.columns:
                print(f"Missing columns for {symbol} {timeframe}")
                return {"archetypes": archetypes, "tiers": tiers}

            # ORACLE: Find Winners
            lookahead_map = {"15m": 48, "1h": 24, "4h": 12, "1d": 7, "1w": 4}
            lookahead = lookahead_map.get(timeframe, 20)
            
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=lookahead)
            df['future_high'] = df['high'].rolling(window=indexer).max().shift(-1)
            df['gain'] = (df['future_high'] - df['close']) / df['close']
            
            # Filter Rallies (>1% for testing, >5% normally)
            # thresholds: 0.05 is default. Lowering to 0.01 to see if data exists.
            candidates = df[df['gain'] >= 0.01].copy()
            print(f"Scanning {symbol} {timeframe}: Found {len(candidates)} candidates (Threshold 1%)")

            if candidates.empty:
                return {"archetypes": archetypes, "tiers": tiers}

            # Deduplication
            dedup_hours = {"15m": 12, "1h": 24, "4h": 48, "1d": 168}.get(timeframe, 24)
            unique_rallies = []
            last_ts = None
            
            for i, row in candidates.iterrows():
                ts = row['timestamp']
                
                if last_ts is not None:
                    diff = ts - last_ts
                    # Ensure diff is positive and check threshold
                    if diff < timedelta(hours=dedup_hours):
                        continue 
                
                last_ts = ts
                unique_rallies.append(row)
                
            # CLASSIFY
            for row in unique_rallies:
                rsi = row['rsi']
                vol = row['volume_rel']
                gain = row['gain']
                gain_pct = gain * 100
                ts = row['timestamp']
                
                item = {
                    "time": ts,
                    "gain": gain_pct,
                    "rsi": rsi,
                    "vol": vol
                }

                # 1. TIER CLASSIFICATION
                if gain >= 0.30: tiers["DIAMOND 💎"].append(item)
                elif gain >= 0.20: tiers["GOLD 🥇"].append(item)
                elif gain >= 0.10: tiers["SILVER 🥈"].append(item)
                elif gain >= 0.05: tiers["BRONZE 🥉"].append(item)
                else: 
                     # Add to Bronze or ignore?
                     # For now, let's keep Bronze >= 5%.
                     # If < 5%, we might need a "STONE" or "DUST" tier if we want to show them.
                     # But UI only shows D/G/S/B.
                     # So items < 5% will appear in "Archetypes" lists (Winners/Losers) but NOT in Tiers tabs.
                     # This is acceptable for debugging "Archetypes" logic, but Tiers will still be empty if no >5%.
                     pass

                # 2. ARCHETYPE CLASSIFICATION
                # Logic v3.0 (Modified: No "THE")
                arch = "OTHER"
                if rsi < 25: arch = "GUILLOTINE"
                elif rsi > 65: arch = "SURFER"
                elif vol >= 5.0: arch = "SUPERNOVA"
                elif vol < 1.5 and rsi < 55: arch = "GRIND"
                elif vol < 1.5 and rsi <= 45: arch = "NINJA"
                
                archetypes[arch].append(item)
                
            return {"archetypes": archetypes, "tiers": tiers}
            
        except Exception as e:
            print(f"Error scanning {symbol} {timeframe}: {e}")
            return {"archetypes": archetypes, "tiers": tiers}
