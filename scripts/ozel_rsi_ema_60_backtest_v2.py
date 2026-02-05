#!/usr/bin/env python3
"""
RSI-EMA > 60 TRIGGER - COIN SPECIFIC BACKTEST (V2)
This script scans all available coin history excluding the year 2026.
It calculates metrics PER COIN and outputs a ranked list.
"""

import pandas as pd
import numpy as np
import os
import json
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
EXCLUDE_YEAR = 2026

def analyze_history_per_coin():
    print(f"🚀 RSI-EMA > 60 COIN BAZLI ANALIZ (2026 HARIÇ)")
    print(f"--------------------------------------------------")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    coin_stats = []
    
    processed_count = 0
    
    for symbol in symbols:
        try:
            # Load 15m Data
            path_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
            if not os.path.exists(path_15m): continue
            
            df_15m = pd.read_parquet(path_15m)
            df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            df_15m.set_index('dt', inplace=True)
            df_15m = df_15m[~df_15m.index.duplicated(keep='last')].sort_index()
            
            # Filter OUT 2026
            df_15m = df_15m[df_15m.index.year < EXCLUDE_YEAR]
            
            if df_15m.empty: continue
            
            # Calculate Indicators
            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            # Trigger Logic: RSI-EMA > 60
            cond_now = df_15m['rsi_ema'] > 60
            triggers = (cond_now) & (~cond_now.shift(1).fillna(False))
            
            trigger_indices = np.where(triggers)[0]
            
            stats = {
                'symbol': symbol,
                'total': 0,
                'wins': 0, # Bronze+
                'fail': 0,
                'neg': 0,
                'diamond': 0,
                'gold': 0,
                'silver': 0,
                'bronze': 0
            }
            
            for idx in trigger_indices:
                entry_price = df_15m['close'].values[idx]
                match_end_idx = min(idx + 49, len(df_15m) - 1)
                
                if match_end_idx <= idx: continue
                
                future_window = df_15m.iloc[idx+1 : match_end_idx+1]
                if future_window.empty: continue
                
                max_price = future_window['high'].max()
                close_price = future_window['close'].iloc[-1]
                
                max_gain_pct = ((max_price - entry_price) / entry_price) * 100
                close_gain_pct = ((close_price - entry_price) / entry_price) * 100
                
                stats['total'] += 1
                
                if max_gain_pct >= 30.0:
                    stats['diamond'] += 1
                    stats['wins'] += 1
                elif max_gain_pct >= 20.0:
                    stats['gold'] += 1
                    stats['wins'] += 1
                elif max_gain_pct >= 10.0:
                    stats['silver'] += 1
                    stats['wins'] += 1
                elif max_gain_pct >= 5.0:
                    stats['bronze'] += 1
                    stats['wins'] += 1
                else:
                    stats['fail'] += 1
                    
                if close_gain_pct < 0:
                    stats['neg'] += 1
            
            if stats['total'] > 0:
                stats['win_rate'] = (stats['wins'] / stats['total']) * 100
                coin_stats.append(stats)
            
            processed_count += 1
            print(f"Processed {symbol}...", end='\r')
            
        except Exception as e:
            continue

    print(f"\n\n==================================================")
    print(f"🏆 EN İYİ PERFORMANS GÖSTERENLER (WIN RATE)")
    print(f"==================================================")
    
    # Sort by Win Rate desc, then Total Signals desc
    coin_stats.sort(key=lambda x: (x['win_rate'], x['total']), reverse=True)
    
    print(f"{'SYMBOL':<10} | {'WIN %':<8} | {'TOT':<5} | {'💎':<4} | {'🥇':<4} | {'🥈':<4} | {'🥉':<4} | {'❌':<5} | {'NEG %':<6}")
    print("-" * 75)
    
    for c in coin_stats:
        # Only show coins with statistically significant samples (> 50 signals) to avoid 1/1=100% bias
        # But user might want to see everything. Let's filter slightly for noise -> > 20 signals
        if c['total'] < 20: continue
        
        neg_rate = (c['neg'] / c['total']) * 100
        print(f"{c['symbol']:<10} | {c['win_rate']:6.2f}% | {c['total']:<5} | {c['diamond']:<4} | {c['gold']:<4} | {c['silver']:<4} | {c['bronze']:<4} | {c['fail']:<5} | {neg_rate:.1f}%")

    print("-" * 75)
    print(f"Toplam listelenen coin sayısı (Sinyal > 20): {len([c for c in coin_stats if c['total'] >= 20])}")
    
    # Save to file for further inspection
    import csv
    keys = coin_stats[0].keys() if coin_stats else []
    if keys:
        with open("rsi_ema_60_coin_stats.csv", "w", newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(coin_stats)
        print(f"\nDetaylı CSV dosyası oluşturuldu: rsi_ema_60_coin_stats.csv")

if __name__ == "__main__":
    analyze_history_per_coin()
