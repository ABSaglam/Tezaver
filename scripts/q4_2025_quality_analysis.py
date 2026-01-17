#!/usr/bin/env python3
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def analyze_q4_2025():
    print("🔍 2025 Q4 (EKİM-ARALIK) KALİTE ANALİZİ")
    print("="*80)
    
    start_date = pd.Timestamp('2025-10-01').tz_localize('UTC')
    end_date = pd.Timestamp('2025-12-31').tz_localize('UTC')
    
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
            
            # Filter Q4
            q4_mask = (df_daily.index >= start_date) & (df_daily.index <= end_date)
            df_q4 = df_daily[q4_mask]
            if df_q4.empty: continue
            
            # Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi'] = calculate_rsi(df_daily['close'])
            
            # Re-sync Indicators to Q4
            df_q4 = df_daily.loc[df_q4.index]
            
            df_15m = pd.read_parquet(path_15m)
            if 'datetime' in df_15m.columns:
                df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                df_15m = df_15m.set_index('datetime')
            if df_15m.index.tz is None: df_15m.index = df_15m.index.tz_localize('UTC')
            
            for d in df_q4.index:
                row = df_q4.loc[d]
                is_trend = (row['atr_pct'] > 15) and (55 < row['rsi'] < 70)
                is_ninja = (12 < row['atr_pct'] <= 15) and (60 < row['rsi'] < 75)
                
                if is_trend or is_ninja:
                    # 3-day outcome
                    window_end = d + pd.Timedelta(days=3)
                    window = df_15m[(df_15m.index > d) & (df_15m.index <= window_end)]
                    
                    if not window.empty:
                        entry = row['close']
                        gain = ((window['high'].max() - entry) / entry) * 100
                        results.append({
                            'date': d,
                            'symbol': symbol,
                            'gain': gain,
                            'atr_pct': row['atr_pct']
                        })
        except: continue

    df_res = pd.DataFrame(results)
    if df_res.empty:
        print("Sinyal bulunamadı.")
        return

    # Aggregate stats
    success_rate = (df_res['gain'] >= 10).mean() * 100
    avg_gain = df_res['gain'].mean()
    avg_atr = df_res['atr_pct'].mean()
    
    print(f"\nSinyal Sayısı:   {len(df_res)}")
    print(f"Başarı (≥%10):  %{success_rate:.1f}")
    print(f"Ort. Kazanç:    %{avg_gain:.1f}")
    print(f"Ort. ATR%:      %{avg_atr:.1f}")
    
    # Monthly breakdown
    print("\n📅 Aylık Başarı:")
    df_res['month'] = df_res['date'].dt.month
    monthly = df_res.groupby('month').agg({
        'gain': ['count', 'mean', lambda x: (x >= 10).mean() * 100]
    })
    monthly.columns = ['Sinyal', 'Ort. Kazanç', 'Başarı %']
    print(monthly)

if __name__ == "__main__":
    analyze_q4_2025()
