#!/usr/bin/env python3
"""
ZEPLİN vs BALON ANALİZİ (zeplin_balon_analysis.py)
--------------------------------------------------
Karşılaştırma:
1. Normal Tünel Sinyali (RSI 55-70, ATR > 12%)
2. "Geç Giriş" (RSI > 70):
   - Haftalık < 50 → BALON (Kaçınılmalı)
   - Haftalık >= 50 → ZEPLİN (Hala Girilebilir)

Amaç: Haftalık RSI filtresinin "geç kaldık" durumlarında ne kadar kurtarıcı olduğunu ölçmek.
"""

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

def run_zeplin_balon_analysis():
    print("🎈 ZEPLİN vs BALON ANALİZİ BAŞLIYOR...")
    
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}

    # Categories
    normal_tunnel_results = []  # RSI 55-70, ATR > 12%
    late_balloon_results = []   # RSI > 70, Weekly < 50
    late_zeplin_results = []    # RSI > 70, Weekly >= 50
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Scanning {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists(): continue
        
        try:
            df_15m = pd.read_parquet(path)
            if len(df_15m) < 2000: continue
            
            # Ensure DatetimeIndex
            if not isinstance(df_15m.index, pd.DatetimeIndex):
                if 'datetime' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                    df_15m = df_15m.set_index('datetime')
                elif 'timestamp' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
                    df_15m = df_15m.set_index('datetime')

            # Weekly & Daily Resample
            df_weekly = df_15m.resample('W-MON').agg({'close': 'last'}).dropna()
            df_weekly['rsi_w'] = calculate_rsi(df_weekly['close'])
            
            df_daily = df_15m.resample('1D').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
            }).dropna()
            
            if len(df_weekly) < 20 or len(df_daily) < 50: continue
            
            # Daily Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi_d'] = calculate_rsi(df_daily['close'])
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            # Helper function to measure outcome
            def measure_outcome(d):
                loc_idx = df_daily.index.get_loc(d)
                if loc_idx + 6 > len(df_daily): return None
                
                entry_price = df_daily.iloc[loc_idx]['close']
                future = df_daily.iloc[loc_idx+1 : loc_idx+6]
                if len(future) < 1: return None
                
                max_price = future['high'].max()
                return ((max_price - entry_price) / entry_price) * 100
            
            # Helper to get weekly RSI context
            def get_weekly_rsi(d):
                prior_weeks = df_weekly[:d]
                if len(prior_weeks) < 1: return None
                return prior_weeks.iloc[-1]['rsi_w']
            
            # Scan all days
            for d in df_daily.index:
                if d < pd.Timestamp("2024-01-01").tz_localize('UTC'): continue
                
                row = df_daily.loc[d]
                rsi_d = row['rsi_d']
                atr_pct = row['atr_pct']
                
                if np.isnan(rsi_d) or np.isnan(atr_pct): continue
                
                gain = measure_outcome(d)
                if gain is None: continue
                
                result_base = {
                    'cluster': cluster,
                    'gain': gain,
                    'is_success': gain > 5,
                    'is_super': gain > 20
                }
                
                # Category 1: Normal Tunnel (RSI 55-70, ATR > 12%)
                is_trend = (atr_pct > 15) and (55 < rsi_d < 70)
                is_ninja = (12 < atr_pct <= 15) and (60 < rsi_d < 75)
                
                if is_trend or is_ninja:
                    normal_tunnel_results.append(result_base.copy())
                
                # Category 2 & 3: Late Entry (RSI > 70)
                if rsi_d > 70:
                    weekly_rsi = get_weekly_rsi(d)
                    if weekly_rsi is None or np.isnan(weekly_rsi): continue
                    
                    if weekly_rsi < 50:
                        late_balloon_results.append(result_base.copy())
                    else:
                        late_zeplin_results.append(result_base.copy())

        except Exception: continue

    # REPORTING
    print("\n" + "="*70)
    print("🎈 ZEPLİN vs BALON KARŞILAŞTIRMA RAPORU (2024-2026)")
    print("="*70)
    
    def report_category(name, data):
        df = pd.DataFrame(data)
        if df.empty:
            print(f"\n{name}: Veri yok.")
            return
            
        print(f"\n{name}:")
        print(f"  Sinyal Sayısı: {len(df)}")
        print(f"  Başarı (>5%):  {df['is_success'].mean()*100:.1f}%")
        print(f"  Süper (>20%):  {df['is_super'].mean()*100:.1f}%")
        print(f"  Ort. Kazanç:   {df['gain'].mean():.1f}%")
        
        # Cluster breakdown
        print("  Kümelere Göre:")
        stats = df.groupby('cluster').agg({
            'is_success': 'mean',
            'gain': 'mean',
            'cluster': 'count'
        })
        stats['is_success'] *= 100
        stats.columns = ['Başarı%', 'Ort.Kazanç', 'Sayı']
        print(stats.to_string(float_format="%.1f"))
    
    report_category("📗 NORMAL TÜNEL (RSI 55-70, ATR >12%)", normal_tunnel_results)
    report_category("🎈 GEÇ GİRİŞ - BALON (RSI >70, Haftalık <50)", late_balloon_results)
    report_category("🛸 GEÇ GİRİŞ - ZEPLİN (RSI >70, Haftalık ≥50)", late_zeplin_results)
    
    # Summary
    print("\n" + "-"*70)
    print("📊 SONUÇ ÖZETİ:")
    
    df_normal = pd.DataFrame(normal_tunnel_results)
    df_balloon = pd.DataFrame(late_balloon_results)
    df_zeplin = pd.DataFrame(late_zeplin_results)
    
    normal_success = df_normal['is_success'].mean()*100 if not df_normal.empty else 0
    balloon_success = df_balloon['is_success'].mean()*100 if not df_balloon.empty else 0
    zeplin_success = df_zeplin['is_success'].mean()*100 if not df_zeplin.empty else 0
    
    print(f"  Normal Tünel Başarısı: {normal_success:.1f}%")
    print(f"  Balon (Kaçınılmalı):   {balloon_success:.1f}%")
    print(f"  Zeplin (Girilebilir):  {zeplin_success:.1f}%")
    print("-"*70)

if __name__ == "__main__":
    run_zeplin_balon_analysis()
