#!/usr/bin/env python3
"""
Check Today's Signals & Annotate with DNA
-----------------------------------------
1. Scans all 441 coins for today's Ayaş Tüneli signals (TREND/NINJA).
2. Annotates them with their Coin DNA Cluster (ROCKET, ACTIVE, etc.).
3. Prints a user-friendly report.
"""

import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_atr(high, low, close, period=14):
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def main():
    print("🔍 CHECKING SIGNALS & DNA...")
    print("=" * 60)
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        # Create map: symbol -> cluster
        dna_map = dict(zip(dna['symbol'], dna['cluster']))
    except Exception as e:
        print("Warning: Could not load DNA. Proceeding without clusters.")
        dna_map = {}

    signals = []
    checked_count = 0
    latest_date = None

    for symbol in DEFAULT_COINS:
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if not path.exists(): continue
        
        try:
            df = pd.read_parquet(path)
            if len(df) < 50: continue
            
            # Find latest date in dataset
            last_date = df['datetime'].max()
            if latest_date is None or last_date > latest_date:
                latest_date = last_date
            
            # Indicators
            df['atr'] = calculate_atr(df['high'], df['low'], df['close'], 14)
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            df['rsi'] = calculate_rsi(df['close'], 14)
            
            # Check Last Candle
            last_row = df.iloc[-1]
            
            # SIGNAL LOGIC
            # TREND: ATR% > 15, 55 < RSI < 70
            is_trend = (last_row['atr_pct'] > 15) and (55 < last_row['rsi'] < 70)
            
            # NINJA: ATR% 12-15, 60 < RSI < 75
            is_ninja = (12 < last_row['atr_pct'] <= 15) and (60 < last_row['rsi'] < 75)
            
            if is_trend or is_ninja:
                sig_type = "TREND" if is_trend else "NINJA"
                cluster = dna_map.get(symbol, "UNKNOWN")
                
                signals.append({
                    'symbol': symbol,
                    'date': last_row['datetime'],
                    'type': sig_type,
                    'cluster': cluster,
                    'close': last_row['close'],
                    'atr_pct': last_row['atr_pct'],
                    'rsi': last_row['rsi']
                })
                
            checked_count += 1
            
        except Exception as e:
            continue

    print(f"Scanned {checked_count} coins. Latest data date: {latest_date}")
    print("-" * 60)
    
    if not signals:
        print("❌ No signals found for today.")
    else:
        # Filter for the actual latest date (ensure we don't show stale signals)
        # Using a tolerance of 24h just in case some coins closed earlier? 
        # Ideally all should be same day.
        today_signals = [s for s in signals if s['date'] == latest_date]
        stale_signals = [s for s in signals if s['date'] != latest_date]

        if today_signals:
            print(f"✅ FOUND {len(today_signals)} SIGNALS for {latest_date.date()}:\n")
            
            # Convert to DF for pretty printing
            df_sig = pd.DataFrame(today_signals)
            
            # Sort: ROCKET first, then ACTIVE, etc.
            cluster_order = {'🚀 ROCKET': 0, '🏃 ACTIVE': 1, '🐢 CALM': 2, '💉 NEEDLE': 3, '= STABLE': 4}
            # Clean cluster string to match keys if needed
            # The CSV has emojis? YES. "🚀 ROCKET"
            
            df_sig['sort_key'] = df_sig['cluster'].map(lambda x: cluster_order.get(x, 99))
            df_sig = df_sig.sort_values('sort_key')
            
            print(df_sig[['symbol', 'cluster', 'type', 'atr_pct', 'rsi']].to_markdown(index=False, floatfmt=".2f"))
            
            # Specific Advice for ROCKETs
            rockets = df_sig[df_sig['cluster'].str.contains('ROCKET', na=False)]
            if not rockets.empty:
                print("\n🚀 ROCKET ALERT! Start 48h Sniper Watch for:")
                for _, r in rockets.iterrows():
                    print(f"   - {r['symbol']} ({r['type']})")
        
        if stale_signals:
            print(f"\n⚠️ Ignored {len(stale_signals)} stale signals from older dates.")

if __name__ == "__main__":
    main()
