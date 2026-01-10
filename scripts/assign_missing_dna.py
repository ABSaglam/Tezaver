import json
import pandas as pd
import numpy as np
from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

def calculate_dna_metrics(symbol):
    """Calculate DNA metrics for a single coin."""
    path_1d = coin_cell_paths.get_history_file(symbol, "1d")
    if not path_1d.exists():
        return None
    
    df = pd.read_parquet(path_1d)
    if len(df) < 30:
        return None
    
    try:
        # Volatility (ATR%)
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift(1)),
                                        abs(df['low'] - df['close'].shift(1))))
        atr = df['tr'].rolling(14).mean().iloc[-1]
        volatility = (atr / df['close'].iloc[-1]) * 100
        
        # Trend Quality (Consecutive green days ratio)
        df['green'] = df['close'] > df['open']
        trend_quality = df['green'].tail(20).sum() / 20 * 100
        
        # Simple composite score
        composite = (volatility * 0.4) + (trend_quality * 0.6)
        
        # Assign tier based on composite
        if composite > 70: tier = 'A'
        elif composite > 55: tier = 'B+'
        elif composite > 45: tier = 'B'
        elif composite > 35: tier = 'B-'
        elif composite > 25: tier = 'C+'
        elif composite > 15: tier = 'C'
        elif composite > 8: tier = 'C-'
        else: tier = 'D'
        
        return {
            'symbol': symbol,
            'volatility': round(volatility, 2),
            'trend_quality': round(trend_quality, 2),
            'composite': round(composite, 2),
            'tier': tier
        }
    except Exception:
        return None

def main():
    # Load existing DNA
    dna_path = 'library/coin_dna_definitive.json'
    existing_dna = json.load(open(dna_path))
    existing_symbols = {d['symbol'] for d in existing_dna}
    
    # Find unmapped coins
    unmapped = [s for s in DEFAULT_COINS if s not in existing_symbols]
    print(f"🧬 Assigning DNA to {len(unmapped)} unmapped coins...")
    
    new_entries = []
    for symbol in unmapped:
        dna = calculate_dna_metrics(symbol)
        if dna:
            new_entries.append(dna)
            print(f"  {symbol}: {dna['tier']} (Composite: {dna['composite']:.1f})")
    
    # Merge and save
    all_dna = existing_dna + new_entries
    with open(dna_path, 'w') as f:
        json.dump(all_dna, f, indent=2)
    
    print(f"\n✅ DNA database updated. Total: {len(all_dna)} coins")
    
    # Show tier distribution
    tiers = {}
    for d in all_dna:
        t = d.get('tier', 'Unknown')
        tiers[t] = tiers.get(t, 0) + 1
    print("\n📊 New Tier Distribution:")
    for t in ['A', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D']:
        print(f"  {t}: {tiers.get(t, 0)}")

if __name__ == "__main__":
    main()
