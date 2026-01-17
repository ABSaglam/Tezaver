#!/usr/bin/env python3
"""
SON 7 GÜNLÜK TÜNEL SİNYALLERİ (last_week_tunnel_signals.py)
===========================================================
Son 7 gün için Ayaş Tüneli sinyallerini listeler.
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

def run_weekly_signals():
    print("🚇 SON 7 GÜNLÜK TÜNEL SİNYALLERİ")
    print("="*70)
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}
    
    # Date range: last 7 days
    today = pd.Timestamp.now(tz='UTC').floor('D')
    start_date = today - pd.Timedelta(days=7)
    
    print(f"Tarih Aralığı: {start_date.strftime('%Y-%m-%d')} - {today.strftime('%Y-%m-%d')}")
    print("-"*70)
    
    results = []
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Tarama: {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if not path.exists():
            # Try 15m and resample
            path_15m = coin_cell_paths.get_history_file(symbol, '15m')
            if not path_15m.exists(): continue
            
            try:
                df_15m = pd.read_parquet(path_15m)
                if 'datetime' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                    df_15m = df_15m.set_index('datetime')
                
                df = df_15m.resample('1D').agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
                }).dropna()
            except:
                continue
        else:
            try:
                df = pd.read_parquet(path)
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    df = df.set_index('datetime')
            except:
                continue
        
        if len(df) < 20: continue
        
        # Calculate indicators
        df['atr_val'] = (df['high'] - df['low']).rolling(14).mean()
        df['atr_pct'] = (df['atr_val'] / df['close']) * 100
        df['rsi'] = calculate_rsi(df['close'])
        
        cluster = dna_map.get(symbol, "UNKNOWN")
        
        # Check last 7 days
        for d in df.index:
            if d.tzinfo is None:
                d_tz = d.tz_localize('UTC')
            else:
                d_tz = d
            
            if d_tz < start_date or d_tz > today: continue
            
            row = df.loc[d]
            rsi = row['rsi']
            atr_pct = row['atr_pct']
            
            if np.isnan(rsi) or np.isnan(atr_pct): continue
            
            # Signal detection
            is_trend = (atr_pct > 15) and (55 < rsi < 70)
            is_ninja = (12 < atr_pct <= 15) and (60 < rsi < 75)
            
            if is_trend or is_ninja:
                results.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'symbol': symbol.replace('USDT', ''),
                    'cluster': cluster,
                    'type': 'TREND' if is_trend else 'NINJA',
                    'rsi': round(rsi, 1),
                    'atr_pct': round(atr_pct, 1),
                    'close': round(row['close'], 4)
                })
    
    print(f"\nTarama tamamlandı. {len(results)} sinyal bulundu.")
    print("="*70)
    
    if not results:
        print("❌ Son 7 günde sinyal bulunamadı.")
        return
    
    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values(['date', 'cluster', 'symbol'])
    
    # Group by date
    for date in sorted(df_res['date'].unique(), reverse=True):
        day_signals = df_res[df_res['date'] == date]
        print(f"\n📅 {date} ({len(day_signals)} sinyal)")
        print("-"*70)
        print(f"{'SYMBOL':<12} {'CLUSTER':<10} {'TYPE':<8} {'RSI':<8} {'ATR%':<8}")
        print("-"*70)
        
        for _, r in day_signals.iterrows():
            print(f"{r['symbol']:<12} {r['cluster']:<10} {r['type']:<8} {r['rsi']:<8} {r['atr_pct']:<8}")
    
    # Save
    df_res.to_csv('library/last_week_tunnel_signals.csv', index=False)
    print(f"\n✅ Kaydedildi: library/last_week_tunnel_signals.csv")

if __name__ == "__main__":
    run_weekly_signals()
