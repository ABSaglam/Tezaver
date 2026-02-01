#!/usr/bin/env python3
"""
YENİ NESİL PORTAKAL SİMÜLASYONU
Kurallar:
1. ang_score > 4
2. trend_score >= 1
3. d_atr > 5
4. ribbon_above == True
"""

import pandas as pd
import numpy as np
import os
import math
import sys

TARGET_START_DATE = "2026-01-15"
TARGET_END_DATE   = "2026-01-31"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def run_simulation():
    print(f"🍊 Yeni Nesil Portakal Simülasyonu Başlıyor...")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_triggers = []
    
    start_d = pd.Timestamp(TARGET_START_DATE)
    end_d = pd.Timestamp(TARGET_END_DATE) + pd.Timedelta(days=1)
    
    for symbol in symbols:
        try:
            # Load Data
            try:
                df_15m = pd.read_parquet(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
                df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
                df_15m.set_index('dt', inplace=True)
                df_15m = df_15m[~df_15m.index.duplicated(keep='last')].sort_index()
                
                df_1d = pd.read_parquet(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
                df_1d['dt'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
                df_1d.set_index('dt', inplace=True)
                df_1d = df_1d[~df_1d.index.duplicated(keep='last')].sort_index()
                
                df_4h = pd.read_parquet(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
                df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
                df_4h.set_index('dt', inplace=True)
                df_4h = df_4h[~df_4h.index.duplicated(keep='last')].sort_index()

                df_1h = pd.read_parquet(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
                df_1h['dt'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
                df_1h.set_index('dt', inplace=True)
                df_1h = df_1h[~df_1h.index.duplicated(keep='last')].sort_index()
            except: continue

            # Indicators
            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
            
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr14'] = d_tr.rolling(window=14).mean()
            df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
            
            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
            rsi_ribbon_cols = []
            for p in ribbon_periods:
                df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
                rsi_ribbon_cols.append(f'rsi_rib_{p}')
            
            ribbon_max = df_15m[rsi_ribbon_cols].max(axis=1)
            rsi_ema = df_15m['rsi_ema']
            cond_now = rsi_ema > ribbon_max
            triggers = (cond_now) & (~cond_now.shift(1).fillna(False))
            all_trigger_indices = np.where(triggers)[0]

            # Iterate
            current = start_d
            while current <= end_d:
                current_utc = current.normalize()
                day_mask = (df_15m.index.normalize() == current_utc)
                day_indices = np.where(day_mask)[0]
                
                if len(day_indices) == 0:
                    current += pd.Timedelta(days=1); continue
                
                try: daily_atr = df_1d['atr_pct'].asof(current_utc)
                except: daily_atr = 0

                for i in day_indices:
                    if i < 21: continue
                    if i not in all_trigger_indices: continue
                    
                    trig_time = df_15m.index[i]
                    
                    # --- RULES CHECK ---
                    
                    # 4. Ribbon Above (Green)
                    val_20 = df_15m['rsi_rib_20'].values[i]
                    val_55 = df_15m['rsi_rib_55'].values[i]
                    ribbon_above = val_20 > val_55
                    
                    # 1. Angle Score
                    val_20_p = df_15m['rsi_rib_20'].values[i-1]
                    val_55_p = df_15m['rsi_rib_55'].values[i-1]
                    curr_v = val_20 if ribbon_above else val_55
                    prev_v = val_20_p if ribbon_above else val_55_p
                    rib_slope = (curr_v - prev_v) / 2.0
                    ang_score = math.degrees(math.atan(rib_slope)) / 4.5
                    
                    # 2. Trend Score
                    c4 = df_4h['close'].asof(trig_time); e4 = df_4h['ema21'].asof(trig_time)
                    c1 = df_1h['close'].asof(trig_time); e1 = df_1h['ema21'].asof(trig_time)
                    t4 = 1 if c4 and e4 and c4 > e4 else 0
                    t1 = 1 if c1 and e1 and c1 > e1 else 0
                    trend_score = t4 + t1
                    
                    # 3. ATR: daily_atr
                    
                    # --- FILTER LOGIC ---
                    passes_filter = True
                    if not ribbon_above: passes_filter = False
                    if ang_score <= 4: passes_filter = False # Strict > 4
                    if trend_score < 1: passes_filter = False
                    if daily_atr <= 5: passes_filter = False
                    
                    # Peak Calc
                    close_p = df_15m['close'].values[i]
                    search_limit = min(i + 22, len(df_15m))
                    if i + 1 < len(df_15m):
                        val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                        if len(val_slice) > 0: peak_price = val_slice.max()
                        else: peak_price = close_p
                    else: peak_price = close_p
                    peak_pct = ((peak_price / close_p) - 1) * 100
                    
                    all_triggers.append({
                        'peak': peak_pct,
                        'passed': passes_filter
                    })
                
                current += pd.Timedelta(days=1)
        except: continue

    df = pd.DataFrame(all_triggers)
    if df.empty: return print("Veri yok.")

    before = df
    after = df[df['passed'] == True]
    
    def calc_stats(d):
        total = len(d)
        if total == 0: return 0, 0, 0
        success = len(d[d['peak'] >= 5])
        rate = (success/total)*100
        return total, success, rate
    
    t1, s1, r1 = calc_stats(before)
    t2, s2, r2 = calc_stats(after)
    
    print(f"\n🍊 SİMÜLASYON SONUÇLARI")
    print("-" * 40)
    print(f"{'DURUM':<15} | {'TETIK':<10} | {'BAŞARILI':<10} | {'ORAN':<10}")
    print("-" * 40)
    print(f"{'ÖNCESİ':<15} | {t1:<10} | {s1:<10} | %{r1:.1f}")
    print(f"{'SONRASI':<15} | {t2:<10} | {s2:<10} | %{r2:.1f}")
    print("-" * 40)
    print(f"Elenen Tetik: {t1-t2} (%{(t1-t2)/t1*100:.1f} gürültü)")
    
    # Tier Breakdown for After
    total = len(after)
    if total > 0:
        diamond = len(after[after['peak'] >= 30])
        gold = len(after[(after['peak'] >= 20) & (after['peak'] < 30)])
        silver = len(after[(after['peak'] >= 10) & (after['peak'] < 20)])
        bronze = len(after[(after['peak'] >= 5) & (after['peak'] < 10)])
        
        print(f"\n Yeni Tier Dağılımı ({total} tetik):")
        print(f" 💎 Elmas (>30%): {diamond} (%{diamond/total*100:.1f})")
        print(f" 🥇 Altın  (>20%): {gold} (%{gold/total*100:.1f})")
        print(f" 🥈 Gümüş  (>10%): {silver} (%{silver/total*100:.1f})")
        print(f" 🥉 Bronz  (>5%):  {bronze} (%{bronze/total*100:.1f})")

if __name__ == "__main__":
    run_simulation()
