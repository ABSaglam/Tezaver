#!/usr/bin/env python3
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

def classify_tier(gain):
    if gain >= 30: return 'DIAMOND'
    if gain >= 20: return 'GOLD'
    if gain >= 10: return 'SILVER'
    if gain >= 5: return 'BRONZE'
    if gain >= 0: return 'IRON'
    return 'NEGATIVE'

def run_96h_analysis():
    print("🚀 AYAŞ TÜNELİ - 96 SAAT (4 GÜN) LİMİTLİ TARİHSEL ANALİZ BAŞLIYOR")
    print("="*80)
    
    start_date = pd.Timestamp('2024-01-01').tz_localize('UTC')
    end_date = pd.Timestamp('2026-01-17').tz_localize('UTC')
    
    results = []
    
    for symbol in DEFAULT_COINS:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        if not path_1d.exists() or not path_15m.exists(): continue
        
        try:
            df_daily = pd.read_parquet(path_1d)
            if 'datetime' in df_daily.columns:
                df_daily['datetime'] = pd.to_datetime(df_daily['datetime'])
                df_daily = df_daily.set_index('datetime')
            if df_daily.index.tz is None: df_daily.index = df_daily.index.tz_localize('UTC')
            
            # Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi'] = calculate_rsi(df_daily['close'])
            
            # Filter range
            mask = (df_daily.index >= start_date) & (df_daily.index <= end_date)
            df_daily = df_daily[mask]
            
            if df_daily.empty: continue
            
            df_15m = pd.read_parquet(path_15m)
            if 'datetime' in df_15m.columns:
                df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                df_15m = df_15m.set_index('datetime')
            if df_15m.index.tz is None: df_15m.index = df_15m.index.tz_localize('UTC')
            
            for d in df_daily.index:
                row = df_daily.loc[d]
                is_trend = (row['atr_pct'] > 15) and (55 < row['rsi'] < 70)
                is_ninja = (12 < row['atr_pct'] <= 15) and (60 < row['rsi'] < 75)
                
                if is_trend or is_ninja:
                    # 96-hour window
                    window_end = d + pd.Timedelta(hours=96)
                    window = df_15m[(df_15m.index > d) & (df_15m.index <= window_end)]
                    
                    if not window.empty:
                        entry = row['close']
                        max_p = window['high'].max()
                        gain = ((max_p - entry) / entry) * 100
                        results.append({
                            'date': d,
                            'symbol': symbol,
                            'gain': gain,
                            'tier': classify_tier(gain)
                        })
        except: continue

    df_res = pd.DataFrame(results)
    if df_res.empty:
        print("Sinyal bulunamadı.")
        return

    df_res['year'] = df_res['date'].dt.year
    df_res['month'] = df_res['date'].dt.month
    
    # DSG success
    df_res['is_dsg'] = df_res['gain'] >= 10
    
    # Monthly aggregate
    monthly = df_res.groupby(['year', 'month']).agg({
        'is_dsg': 'mean',
        'gain': 'mean',
        'symbol': 'count'
    }).rename(columns={'is_dsg': 'Success %', 'gain': 'Avg Gain %', 'symbol': 'Count'})
    
    monthly['Success %'] *= 100
    
    # Add Tier columns
    for t in ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON']:
        monthly[t] = df_res[df_res['tier'] == t].groupby(['year', 'month']).size()
    monthly = monthly.fillna(0).astype({'Count': int, 'DIAMOND': int, 'GOLD': int, 'SILVER': int, 'BRONZE': int, 'IRON': int})
    
    print("\n✅ 96 SAAT KURALINA GÖRE GÜNCEL AYLIK PERFORMANS")
    print(monthly)
    
    # Save results
    monthly.to_csv('library/tunnel_96h_monthly_stats.csv')
    df_res.to_csv('library/tunnel_96h_all_signals.csv', index=False)
    print(f"\nSonuçlar kaydedildi: library/tunnel_96h_monthly_stats.csv")

if __name__ == "__main__":
    run_96h_analysis()
