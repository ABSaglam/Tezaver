#!/usr/bin/env python3
"""
AYAŞ TÜNELİ + RALLYSTORE ANALİZİ (tunnel_rallystore_analysis.py)
================================================================
RallyStore'daki gerçek rallilerle Tünel sinyallerini eşleştir.

Tier Eşikleri (Doğru):
- Diamond: ≥30%
- Gold: 20-30%
- Silver: 10-20%
- Bronze: 5-10%
- Iron: 0-5%
- Negatiflerde tam tersi
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths, config
from tezaver.core.rally_store import RallyStore

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def classify_tier(gain_pct):
    """Doğru tier sınıflandırması"""
    if gain_pct >= 30: return 'DIAMOND'
    if gain_pct >= 20: return 'GOLD'
    if gain_pct >= 10: return 'SILVER'
    if gain_pct >= 5: return 'BRONZE'
    if gain_pct >= 0: return 'IRON'
    if gain_pct >= -5: return '-IRON'
    if gain_pct >= -10: return '-BRONZE'
    if gain_pct >= -20: return '-SILVER'
    if gain_pct >= -30: return '-GOLD'
    return '-DIAMOND'

def run_tunnel_rallystore_analysis():
    print("📊 AYAŞ TÜNELİ + RALLYSTORE ANALİZİ BAŞLIYOR...")
    print("="*70)
    
    store = RallyStore()
    start_date = pd.Timestamp("2024-01-01").tz_localize('UTC')
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}

    results = []
    
    for idx, symbol in enumerate(config.DEFAULT_COINS):
        if idx % 50 == 0: print(f"Tarama: {idx}/{len(config.DEFAULT_COINS)}...", end='\r')
        
        # 1. Get Daily Data for Signal Detection
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        if not path_15m.exists(): continue
        
        try:
            df_15m = pd.read_parquet(path_15m)
            if len(df_15m) < 1000: continue
            
            # Ensure DatetimeIndex
            if not isinstance(df_15m.index, pd.DatetimeIndex):
                if 'datetime' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                    df_15m = df_15m.set_index('datetime')
            
            # Resample to Daily
            df_daily = df_15m.resample('1D').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
            }).dropna()
            
            if len(df_daily) < 50: continue
            
            # Daily Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi_d'] = calculate_rsi(df_daily['close'])
            
            # 2. Get Rallies from RallyStore (15m timeframe)
            rallies = store.list_rallies(symbol=symbol, timeframe='15m')
            
            if not rallies:
                continue
            
            # Create rally lookup: date -> gain_pct (from raw_data.future_max_gain_pct)
            rally_lookup = {}
            for r in rallies:
                try:
                    r_time = pd.Timestamp(r.get('event_time'))
                    if r_time.tzinfo is None:
                        r_time = r_time.tz_localize('UTC')
                    r_date = r_time.floor('D')
                    
                    # Get gain from raw_data
                    raw = r.get('raw_data', {})
                    gain_pct = raw.get('future_max_gain_pct', 0)
                    if gain_pct is None: gain_pct = 0
                    gain_pct = gain_pct * 100  # Convert 0.36 -> 36%
                    
                    # Keep highest gain for that day
                    if r_date not in rally_lookup or gain_pct > rally_lookup[r_date]:
                        rally_lookup[r_date] = gain_pct
                except:
                    continue
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            # 3. Check each day for signal + rally match
            for d in df_daily.index:
                if d < start_date: continue
                
                row = df_daily.loc[d]
                rsi_d = row['rsi_d']
                atr_pct = row['atr_pct']
                
                if np.isnan(rsi_d) or np.isnan(atr_pct): continue
                
                # Signal Detection (Only TREND and NINJA - No Zeplin)
                is_trend = (atr_pct > 15) and (55 < rsi_d < 70)
                is_ninja = (12 < atr_pct <= 15) and (60 < rsi_d < 75)
                
                if not (is_trend or is_ninja): continue
                
                signal_type = "TREND" if is_trend else "NINJA"
                
                # 4. Check for rally in the next 3 days (72h window)
                found_gain = None
                for day_offset in range(0, 4):  # Same day to +3 days
                    check_date = d + pd.Timedelta(days=day_offset)
                    if check_date in rally_lookup:
                        check_gain = rally_lookup[check_date]
                        if found_gain is None or check_gain > found_gain:
                            found_gain = check_gain
                
                # If rally found, calculate tier from gain
                if found_gain is not None:
                    final_gain = found_gain
                    tier = classify_tier(final_gain)
                else:
                    # No rally found - ALWAYS negative tier based on max_loss
                    window_start = d
                    window_end = d + pd.Timedelta(days=3)
                    window_data = df_15m[(df_15m.index > window_start) & (df_15m.index <= window_end)]
                    
                    if len(window_data) < 10: continue
                    
                    entry_price = row['close']
                    min_price = window_data['low'].min()
                    max_loss = ((min_price - entry_price) / entry_price) * 100
                    
                    final_gain = max_loss
                    if max_loss >= -5: tier = '-IRON'
                    elif max_loss >= -10: tier = '-BRONZE'
                    elif max_loss >= -20: tier = '-SILVER'
                    elif max_loss >= -30: tier = '-GOLD'
                    else: tier = '-DIAMOND'
                
                results.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'symbol': symbol,
                    'cluster': cluster,
                    'signal_type': signal_type,
                    'gain': final_gain,
                    'tier': tier
                })
                
        except Exception as e:
            continue

    print(f"\nTarama tamamlandı. Toplam sinyal: {len(results)}")
    
    # Generate Report
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print("❌ Hiç sinyal bulunamadı.")
        return
    
    # Tier Distribution
    tier_order = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON', '-IRON', '-BRONZE', '-SILVER', '-GOLD', '-DIAMOND']
    total = len(df_res)
    
    print("\n" + "="*70)
    print("🚇 AYAŞ TÜNELİ - 2 Yıllık 15m Ralli Analizi")
    print(f"Toplam Sinyal: {total}")
    print("="*70)
    
    print("\n| Tier | Sayı | Oran |")
    print("|:---|---:|---:|")
    
    for t in tier_order:
        count = len(df_res[df_res['tier'] == t])
        pct = count / total * 100 if total > 0 else 0
        print(f"| {t} | {count} | %{pct:.1f} |")
    
    # Summary
    positive_tiers = ['DIAMOND', 'GOLD', 'SILVER']
    neutral_tiers = ['BRONZE', 'IRON']
    negative_tiers = ['-IRON', '-BRONZE', '-SILVER', '-GOLD', '-DIAMOND']
    
    pos_count = len(df_res[df_res['tier'].isin(positive_tiers)])
    neu_count = len(df_res[df_res['tier'].isin(neutral_tiers)])
    neg_count = len(df_res[df_res['tier'].isin(negative_tiers)])
    
    print("\n📊 Özet:")
    print(f"  Ralli (D+G+S): {pos_count} (%{pos_count/total*100:.1f})")
    print(f"  Nötr (B+I):    {neu_count} (%{neu_count/total*100:.1f})")
    print(f"  Kayıp (-tier): {neg_count} (%{neg_count/total*100:.1f})")
    
    # Save
    df_res.to_csv('library/tunnel_rallystore_results.csv', index=False)
    print(f"\n✅ Sonuçlar kaydedildi: library/tunnel_rallystore_results.csv")

if __name__ == "__main__":
    run_tunnel_rallystore_analysis()
