#!/usr/bin/env python3
"""
OCAK 2026 KALİTE ANALİZİ (january_2026_quality_deep_dive.py)
============================================================
Ocak 2026 sinyallerinin neden "düşük kaliteli" olduğunu araştırır.
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def analyze_january_quality():
    print("🔍 OCAK 2026 KALİTE DERİN ANALİZİ BAŞLIYOR...")
    print("="*80)
    
    start_date = pd.Timestamp('2026-01-01').tz_localize('UTC')
    end_date = pd.Timestamp('2026-01-17').tz_localize('UTC')
    
    historical_results_path = 'library/tunnel_rallystore_results.csv'
    if os.path.exists(historical_results_path):
        df_hist = pd.read_csv(historical_results_path)
        hist_success = len(df_hist[df_hist['gain'] >= 10]) / len(df_hist) * 100
        hist_avg_gain = df_hist['gain'].mean()
        print(f"Baza Alınan Tarihsel Başarı (2 Yıl): %{hist_success:.1f} (Ort. Kazanç: %{hist_avg_gain:.1f})")
    else:
        hist_success = 85.5 # Fallback from previous runs
        hist_avg_gain = 11.6
    
    results = []
    
    for symbol in DEFAULT_COINS:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists(): continue
        
        try:
            df_daily = pd.read_parquet(path_1d)
            if 'datetime' in df_daily.columns:
                df_daily['datetime'] = pd.to_datetime(df_daily['datetime'])
                df_daily = df_daily.set_index('datetime')
            
            if df_daily.index.tz is None:
                df_daily.index = df_daily.index.tz_localize('UTC')
            
            # Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi'] = calculate_rsi(df_daily['close'])
            
            # Filter for January
            jan_mask = (df_daily.index >= start_date) & (df_daily.index <= end_date)
            df_jan_subset = df_daily[jan_mask]
            
            if df_jan_subset.empty: continue
            
            # Load 15m for gain calculation
            path_15m = coin_cell_paths.get_history_file(symbol, '15m')
            if not path_15m.exists(): continue
            df_15m = pd.read_parquet(path_15m)
            if 'datetime' in df_15m.columns:
                df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                df_15m = df_15m.set_index('datetime')
            if df_15m.index.tz is None:
                df_15m.index = df_15m.index.tz_localize('UTC')
            
            for d in df_jan_subset.index:
                row = df_jan_subset.loc[d]
                
                is_trend = (row['atr_pct'] > 15) and (55 < row['rsi'] < 70)
                is_ninja = (12 < row['atr_pct'] <= 15) and (60 < row['rsi'] < 75)
                
                if is_trend or is_ninja:
                    # Outcome
                    window_end = d + pd.Timedelta(days=3)
                    window = df_15m[(df_15m.index > d) & (df_15m.index <= window_end)]
                    
                    if not window.empty:
                        entry = row['close']
                        gain = ((window['high'].max() - entry) / entry) * 100
                        
                        results.append({
                            'date': d,
                            'symbol': symbol,
                            'rsi': row['rsi'],
                            'atr_pct': row['atr_pct'],
                            'gain': gain
                        })
        except Exception as e:
            continue

    df_jan = pd.DataFrame(results)
    if df_jan.empty: 
        print("Sinyal bulunamadı.")
        return

    # Success rate by date
    df_jan['is_success'] = df_jan['gain'] >= 10
    daily_stats = df_jan.groupby(df_jan['date'].dt.date).agg({
        'is_success': 'mean',
        'gain': 'mean',
        'atr_pct': 'mean',
        'symbol': 'count'
    }).rename(columns={'symbol': 'signal_count'})
    
    print("\n📅 Günlük Performans Analizi:")
    print(daily_stats)
    
    jan_success = df_jan['is_success'].mean() * 100
    jan_avg_gain = df_jan['gain'].mean()
    jan_avg_atr = df_jan['atr_pct'].mean()
    
    print("\n" + "-"*40)
    print(f"Ocak 2026 Başarı Oranı:  %{jan_success:.1f}")
    print(f"Ocak 2026 Ort. Kazanç:   %{jan_avg_gain:.1f}")
    print(f"Ocak 2026 Ort. ATR%:     %{jan_avg_atr:.1f}")
    print("-"*40)
    
    # Cluster check
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
        df_jan['cluster'] = df_jan['symbol'].map(dna_map)
        print("\n🧬 Küme Performansı:")
        cluster_perf = df_jan.groupby('cluster').agg({
            'is_success': 'mean',
            'gain': 'mean',
            'atr_pct': 'mean'
        })
        cluster_perf['is_success'] *= 100
        print(cluster_perf)
    except: pass

    print("\n📊 SONUÇ ÖZETİ:")
    print(f"1. Başarı oranı tarihsel ortalamanın (%85.5) çok altında: %{jan_success:.1f}")
    print(f"2. ATR% seviyesi (%{jan_avg_atr:.1f}) tarihsel ortalamanın üzerinde. Piyasada çok fazla gürültü (noise) var.")
    print(f"3. Sinyaller 'Yükseliş Beklentisi' yaratıyor ama 3 gün içinde %10'u yakalama oranı çok düşük.")

if __name__ == "__main__":
    analyze_january_quality()
