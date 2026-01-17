#!/usr/bin/env python3
"""
SON 7 GÜN SİNYAL SONUÇLARI (weekly_signal_outcomes.py)
======================================================
Her sinyalin 3 günlük sonucunu hesaplar.
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def classify_tier(gain_pct):
    if gain_pct >= 30: return '💎 DIAMOND'
    if gain_pct >= 20: return '🥇 GOLD'
    if gain_pct >= 10: return '🥈 SILVER'
    if gain_pct >= 5: return '🥉 BRONZE'
    if gain_pct >= 0: return '🔩 IRON'
    if gain_pct >= -5: return '❌ -IRON'
    if gain_pct >= -10: return '❌ -BRONZE'
    if gain_pct >= -20: return '❌ -SILVER'
    if gain_pct >= -30: return '❌ -GOLD'
    return '❌ -DIAMOND'

def run_signal_outcomes():
    print("📊 SON 7 GÜN SİNYAL SONUÇLARI")
    print("="*80)
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}
    
    today = pd.Timestamp.now(tz='UTC').floor('D')
    start_date = today - pd.Timedelta(days=7)
    
    results = []
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Tarama: {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        # Get 15m data for precise calculation
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        
        if not path_15m.exists(): continue
        
        try:
            df_15m = pd.read_parquet(path_15m)
            if 'datetime' in df_15m.columns:
                df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                df_15m = df_15m.set_index('datetime')
            
            # Daily data for signal detection
            if path_1d.exists():
                df_daily = pd.read_parquet(path_1d)
                if 'datetime' in df_daily.columns:
                    df_daily['datetime'] = pd.to_datetime(df_daily['datetime'])
                    df_daily = df_daily.set_index('datetime')
            else:
                df_daily = df_15m.resample('1D').agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
                }).dropna()
            
            if len(df_daily) < 20 or len(df_15m) < 500: continue
            
            # Calculate indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi'] = calculate_rsi(df_daily['close'])
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            # Check last 7 days for signals
            for d in df_daily.index:
                if d.tzinfo is None:
                    d_tz = d.tz_localize('UTC')
                else:
                    d_tz = d
                
                if d_tz < start_date or d_tz > today: continue
                
                row = df_daily.loc[d]
                rsi = row['rsi']
                atr_pct = row['atr_pct']
                
                if np.isnan(rsi) or np.isnan(atr_pct): continue
                
                # Signal detection
                is_trend = (atr_pct > 15) and (55 < rsi < 70)
                is_ninja = (12 < atr_pct <= 15) and (60 < rsi < 75)
                
                if not (is_trend or is_ninja): continue
                
                # Calculate 3-day outcome from 15m data
                window_start = d
                window_end = d + pd.Timedelta(days=3)
                
                # Ensure we have data for outcome
                window_data = df_15m[(df_15m.index > window_start) & (df_15m.index <= window_end)]
                
                if len(window_data) < 10:
                    outcome = "⏳ (Beklemede)"
                    tier = "⏳"
                    max_gain = None
                else:
                    entry_price = row['close']
                    max_price = window_data['high'].max()
                    min_price = window_data['low'].min()
                    
                    max_gain = ((max_price - entry_price) / entry_price) * 100
                    max_loss = ((min_price - entry_price) / entry_price) * 100
                    
                    # Determine outcome
                    if max_gain >= 10:
                        tier = classify_tier(max_gain)
                        outcome = f"+{max_gain:.1f}%"
                    elif max_gain >= 0:
                        tier = classify_tier(max_gain)
                        outcome = f"+{max_gain:.1f}%"
                    else:
                        tier = classify_tier(max_loss)
                        outcome = f"{max_loss:.1f}%"
                
                results.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'symbol': symbol.replace('USDT', ''),
                    'cluster': cluster,
                    'type': 'TREND' if is_trend else 'NINJA',
                    'rsi': round(rsi, 1),
                    'atr_pct': round(atr_pct, 1),
                    'tier': tier,
                    'outcome': outcome,
                    'max_gain': max_gain
                })
                
        except Exception as e:
            continue
    
    print(f"\nTarama tamamlandı. {len(results)} sinyal.")
    
    if not results:
        print("Sinyal bulunamadı.")
        return
    
    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values(['date', 'cluster', 'symbol'])
    
    # Report by date
    print("\n" + "="*80)
    print("📅 GÜN GÜN SİNYAL SONUÇLARI")
    print("="*80)
    
    for date in sorted(df_res['date'].unique(), reverse=True):
        day_signals = df_res[df_res['date'] == date]
        
        # Count outcomes
        rally_count = len(day_signals[day_signals['tier'].str.contains('DIAMOND|GOLD|SILVER', na=False)])
        total = len(day_signals)
        
        print(f"\n📅 {date} | {total} sinyal | {rally_count} ralli (%{rally_count/total*100:.0f})")
        print("-"*80)
        print(f"{'SYMBOL':<10} {'CLUSTER':<8} {'TYPE':<6} {'RSI':<6} {'ATR%':<6} {'SONUÇ':<12} {'TİER'}")
        print("-"*80)
        
        for _, r in day_signals.iterrows():
            print(f"{r['symbol']:<10} {r['cluster']:<8} {r['type']:<6} {r['rsi']:<6} {r['atr_pct']:<6.1f} {r['outcome']:<12} {r['tier']}")
    
    # Summary
    print("\n" + "="*80)
    print("📊 ÖZET")
    print("="*80)
    
    completed = df_res[df_res['max_gain'].notna()]
    if not completed.empty:
        rally = len(completed[completed['max_gain'] >= 10])
        total = len(completed)
        print(f"Tamamlanan Sinyaller: {total}")
        print(f"Ralli (≥%10): {rally} (%{rally/total*100:.1f})")
    
    # Save
    df_res.to_csv('library/weekly_signal_outcomes.csv', index=False)
    print(f"\n✅ Kaydedildi: library/weekly_signal_outcomes.csv")

if __name__ == "__main__":
    run_signal_outcomes()
