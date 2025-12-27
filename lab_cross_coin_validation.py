
import pandas as pd
from pathlib import Path

def validate_cross_coin():
    coins = ["ADAUSDT", "ETHUSDT", "SOLUSDT"]
    root_dir = Path("/Users/alisaglam/TezaverMac/coin_cells")
    
    print("🌍 CROSS-COIN ARCHETYPE VALIDATION")
    print("Testing 'Supernova' vs 'Grind' fit on Major Rallies (>20%)")
    print("="*80)
    print(f"{'COIN':<8} | {'RALLIES':<8} | {'SUPERNOVA':<10} | {'GRIND':<10} | {'UNMATCHED':<10} | {'COVERAGE'}")
    print("-" * 80)
    
    for symbol in coins:
        feat_path = root_dir / symbol / "data" / "features_15m.parquet"
        if not feat_path.exists(): continue
        
        try:
            df = pd.read_parquet(feat_path)
            if 'rsi_15m' in df.columns: df['rsi'] = df['rsi_15m']
            if 'volume_rel_15m' in df.columns: df['volume_rel'] = df['volume_rel_15m']
            elif 'vol_rel' in df.columns: df['volume_rel'] = df['vol_rel']
            
            # Oracle Lookahead for >20% gain
            lookahead = 48 
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=lookahead)
            df['gain'] = (df['high'].rolling(window=indexer).max().shift(-1) - df['close']) / df['close']
            
            majors = df[df['gain'] >= 0.20].copy()
            total = len(majors)
            if total == 0: continue
            
            # STRICT DEFINITIONS (No Forcing)
            # Supernova: Vol >= 4.0
            # Grind: Vol <= 1.5
            
            n_super = len(majors[majors['volume_rel'] >= 4.0])
            n_grind = len(majors[majors['volume_rel'] <= 1.5])
            
            # Note: A rally could be neither (Vol 1.5 - 4.0) -> UNMATCHED
            # Or both? No, exclusive ranges.
            
            n_matched = n_super + n_grind
            n_unmatched = total - n_matched
            cov_pct = (n_matched / total) * 100
            
            print(f"{symbol:<8} | {total:<8} | {n_super:<10} | {n_grind:<10} | {n_unmatched:<10} | {cov_pct:.1f}%")
            
        except Exception:
            continue

    print("-" * 80)
    print("NOTE: 'Unmatched' means Volume was between 1.5x and 4.0x (The Grey Zone).")

if __name__ == "__main__":
    validate_cross_coin()
