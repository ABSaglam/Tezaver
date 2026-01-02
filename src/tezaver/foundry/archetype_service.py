
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

    @staticmethod
    def analyze_trend_scores(rsi_window: List[float], vol_window: List[float]) -> List[Dict]:
        """
        Analyze Trend and score ALL archetypes.
        Returns sorted list of matches: [{'arch': 'GRIND', 'conf': 85, 'reason': '...'}, ...]
        """
        results = []
        if not rsi_window or not vol_window:
             return []
             
        curr_rsi = rsi_window[-1]
        curr_vol = vol_window[-1]
        n_bars = len(rsi_window)
        
        # Helper: Avg
        def avg(arr, n=10):
            sub = arr[-n:]
            return sum(sub)/len(sub) if sub else 0
            
        avg_vol_20 = avg(vol_window, 20)
        
        # 1. PHOENIX Logic
        if n_bars >= 30:
            min_rsi = min(rsi_window)
            idx_min = rsi_window.index(min_rsi)
            bars_since_low = n_bars - 1 - idx_min
            if min_rsi < 30 and curr_rsi > 40 and 5 <= bars_since_low <= 50:
                 results.append({
                     "arch": "PHOENIX", 
                     "conf": 88, 
                     "reason": f"Recovered from RSI {min_rsi:.0f} (Ashes) in last {bars_since_low} bars"
                 })
                 
        # 2. GUILLOTINE
        if curr_rsi < 35:
             dist = 35 - curr_rsi
             conf = 50 + (dist / 35 * 50)
             results.append({
                 "arch": "GUILLOTINE",
                 "conf": min(99, int(conf)),
                 "reason": f"RSI {curr_rsi:.1f} < 35 (Oversold/Falling)"
             })

        # 3. SUPERNOVA
        if curr_vol >= 5.0:
             results.append({"arch": "SUPERNOVA", "conf": 90, "reason": f"Vol {curr_vol:.1f} (Explosion)"})
             
        # 4. SURFER
        if curr_rsi > 60:
             results.append({"arch": "SURFER", "conf": 85, "reason": f"RSI {curr_rsi:.1f} > 60 (Trend)"})
             
        # 5. NINJA
        if avg_vol_20 < 1.3 and curr_rsi <= 55:
             results.append({"arch": "NINJA", "conf": 85, "reason": f"AvgVol {avg_vol_20:.1f} (Stealth) & RSI {curr_rsi:.0f}"})
             
        # 6. GRIND
        if avg_vol_20 < 1.8:
             results.append({"arch": "GRIND", "conf": 80, "reason": f"AvgVol {avg_vol_20:.1f} (Accumulation)"})
             
        # Sort by Confidence Descending
        results.sort(key=lambda x: x['conf'], reverse=True)
        return results

    @staticmethod
    def classify_trend(rsi_window: List[float], vol_window: List[float]):
        """Legacy Wrapper: Returns best match"""
        scores = ArchetypeService.analyze_trend_scores(rsi_window, vol_window)
        if scores:
            best = scores[0]
            return best['arch'], best['reason'], best['conf']
        return None, "No clear pattern", 0
        
    # Legacy wrapper for vector calls
    @staticmethod
    def classify_vector(rsi, vol):
        return ArchetypeService.classify_trend([rsi]*60, [vol]*60)

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
            "PHOENIX": [], "NINJA": [], "SURFER": []
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
                # Use shared helper
                arch, reason, conf = ArchetypeService.classify_vector(rsi, vol)
                
                # We only need 'arch' for this dict structure unless we want to store confidence too later
                archetypes[arch].append(item)
                
            return {"archetypes": archetypes, "tiers": tiers}
            
        except Exception as e:
            print(f"Error scanning {symbol} {timeframe}: {e}")
            return {"archetypes": archetypes, "tiers": tiers}
