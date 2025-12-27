
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta

def scan_all_coins_archetypes():
    root_dir = Path("/Users/alisaglam/TezaverMac/coin_cells")
    coins = [d.name for d in root_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    coins.sort()
    
    print(f"🌍 MULTI-COIN ARCHETYPE SCAN ({len(coins)} Coins)")
    print("Searching for 'Diamond/Gold' (>20%) Rallies and classifying them...")
    print("="*80)
    print(f"{'SYMBOL':<10} | {'TOTAL RALLIES':<13} | {'DOMINANT ARCHETYPE':<20} | {'PROFILE DETAILS'}")
    print("-" * 80)
    
    for symbol in coins:
        feat_path = root_dir / symbol / "data" / "features_15m.parquet"
        if not feat_path.exists():
            continue
            
        try:
            df = pd.read_parquet(feat_path)
            
            # Normalize Columns
            if 'rsi_15m' in df.columns: df['rsi'] = df['rsi_15m']
            if 'volume_rel_15m' in df.columns: df['volume_rel'] = df['volume_rel_15m']
            if 'vol_rel' in df.columns: df['volume_rel'] = df['vol_rel']
            
            if 'rsi' not in df.columns or 'volume_rel' not in df.columns:
                continue

            # ORACLE: Find Winners
            lookahead = 48 # 12h
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=lookahead)
            df['future_high'] = df['high'].rolling(window=indexer).max().shift(-1)
            df['gain'] = (df['future_high'] - df['close']) / df['close']
            
            # Filter: Only start of rallies (Gain > 20%)
            # To avoid capturing every bar of a rally, we filter local bottoms roughly
            # or just take every bar that offers >20% gain.
            # For "Archetype Personality", taking every signal is okay, but deduplication is better.
            # Let's take ALL signals > 20% to see "Availability"
            
            winners = df[df['gain'] >= 0.20].copy()
            if winners.empty:
                print(f"{symbol:<10} | {'0':<13} | {'-':<20} | No Rallies found.")
                continue
                
            # CLASSIFICATION
            def classify(row):
                rsi = row['rsi']
                vol = row['volume_rel']
                
                # Simple Archetype Logic
                if rsi < 25: return "GUILLOTINE 🩸"
                if rsi > 65: return "SURFER 🏄‍♂️"
                if vol >= 5.0: return "SUPERNOVA 💥"
                if vol < 1.5 and rsi < 45: return "GRIND 🪜"
                
                # Remaining are Hybrids/Phoenix candidates (Phoenix needs time context, skipping for speed)
                return "HYBRID 🧬"
                
            winners['archetype'] = winners.apply(classify, axis=1)
            
            # PROFILE
            counts = winners['archetype'].value_counts()
            total = len(winners)
            dominant = counts.index[0]
            dom_pct = counts.iloc[0] / total * 100
            
            details = []
            for k, v in counts.head(3).items():
                details.append(f"{k} ({v/total*100:.0f}%)")
            
            print(f"{symbol:<10} | {total:<13} | {dominant:<20} | {', '.join(details)}")
            
        except Exception as e:
            # print(f"Error {symbol}: {e}")
            pass

if __name__ == "__main__":
    scan_all_coins_archetypes()
