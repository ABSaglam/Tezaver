#!/usr/bin/env python3
"""
RSI-EMA BAŞARI FAKTÖRLERİ ANALİZİ
Amaç: Başarılı (Peak >= 5%) ve Başarısız (Peak < 5%) tetikleri ayıran özellikleri bulmak.
"""

import pandas as pd
import numpy as np
import os
import math
import sys

TARGET_START_DATE = "2026-01-15"
TARGET_END_DATE   = "2026-01-31"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def run_factor_analysis():
    print(f"🕵️‍♂️ Başarı Faktörleri Analizi Başlıyor...")
    print(f"Tarih: {TARGET_START_DATE} - {TARGET_END_DATE}")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    data_points = []
    
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

            # --- Indicators Calculation ---
            
            # 1. EMAs for Trend
            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
            
            # 2. Daily ATR & ADX
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr14'] = d_tr.rolling(window=14).mean()
            df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
            
            plus_dm = df_1d['high'].diff()
            minus_dm = -df_1d['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            tr14 = d_tr.rolling(window=14).sum()
            plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14)
            minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
            df_1d['adx14'] = dx.rolling(window=14).mean()
            
            # 3. 15m RSI & Ribbon
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

            # 4. 15m MACD
            ema12 = df_15m['close'].ewm(span=12, adjust=False).mean()
            ema26 = df_15m['close'].ewm(span=26, adjust=False).mean()
            df_15m['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()

            # 5. 15m ATR & Volume Metrics
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['atr21'] = tr.rolling(window=21).mean()
            df_15m['tr'] = tr

            # --- Trigger Logic ---
            ribbon_max = df_15m[rsi_ribbon_cols].max(axis=1)
            rsi_ema = df_15m['rsi_ema']
            cond_now = rsi_ema > ribbon_max
            triggers = (cond_now) & (~cond_now.shift(1).fillna(False))
            all_trigger_indices = np.where(triggers)[0]

            # Iterate days
            current = start_d
            while current <= end_d:
                current_utc = current.normalize()
                day_mask = (df_15m.index.normalize() == current_utc)
                day_indices = np.where(day_mask)[0]
                
                if len(day_indices) == 0:
                    current += pd.Timedelta(days=1); continue

                # Daily Context Caching
                try: daily_atr = df_1d['atr_pct'].asof(current_utc)
                except: daily_atr = 0
                try: daily_adx = df_1d['adx14'].asof(current_utc)
                except: daily_adx = 0

                for i in day_indices:
                    if i < 21: continue
                    if i not in all_trigger_indices: continue
                    
                    # Peak Calc
                    close_p = df_15m['close'].values[i]
                    search_limit = min(i + 22, len(df_15m))
                    if i + 1 < len(df_15m):
                        val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                        if len(val_slice) > 0: peak_price = val_slice.max()
                        else: peak_price = close_p
                    else: peak_price = close_p
                    
                    peak_pct = ((peak_price / close_p) - 1) * 100
                    
                    # --- Feature Extraction ---
                    trig_time = df_15m.index[i]
                    
                    # Trend
                    c4 = df_4h['close'].asof(trig_time); e4 = df_4h['ema21'].asof(trig_time)
                    c1 = df_1h['close'].asof(trig_time); e1 = df_1h['ema21'].asof(trig_time)
                    
                    t4 = 1 if c4 and e4 and c4 > e4 else 0
                    t1 = 1 if c1 and e1 and c1 > e1 else 0
                    trend_score = t4 + t1
                    
                    # Volume Metrics
                    try:
                        v_idx = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr100'].values[i] or 0.001)) * 3.33)
                        v_dyn = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr21'].values[i] or 0.001)) * 3.33)
                        
                        past_vidx = []
                        for k in range(1, 4):
                             p_tr = df_15m['tr'].values[i-k]
                             p_atr = df_15m['atr100'].values[i-k] or 0.001
                             past_vidx.append((p_tr/p_atr)*3.33)
                        avg_past_vidx = np.mean(past_vidx) if past_vidx else 0.001
                        v_mom = (v_idx / avg_past_vidx) if avg_past_vidx > 0 else 0
                        
                        body = abs(df_15m['close'].values[i] - df_15m['open'].values[i])
                        rng = df_15m['tr'].values[i] or 0.001
                        v_eff = (body / rng) * 10.0
                        
                        rsi_val = df_15m['rsi'].values[i]
                        v_hyb = min(15.0, v_idx * (rsi_val/50.0))
                    except: continue

                    # RSI Angle
                    rsi_now = df_15m['rsi_ema'].values[i]
                    rsi_prev = df_15m['rsi_ema'].values[i-1]
                    slope = rsi_now - rsi_prev
                    rsi_angle = math.degrees(math.atan(slope))
                    
                    # Ribbon Angle (20 vs 55)
                    val_20 = df_15m['rsi_rib_20'].values[i]
                    val_55 = df_15m['rsi_rib_55'].values[i]
                    val_20_p = df_15m['rsi_rib_20'].values[i-1]
                    val_55_p = df_15m['rsi_rib_55'].values[i-1]
                    
                    ribbon_above = val_20 > val_55
                    curr_v = val_20 if ribbon_above else val_55
                    prev_v = val_20_p if ribbon_above else val_55_p
                    rib_slope = (curr_v - prev_v) / 2.0
                    ang_score = math.degrees(math.atan(rib_slope)) / 4.5
                    
                    data_points.append({
                        'peak': peak_pct,
                        'is_success': 1 if peak_pct >= 5.0 else 0,
                        'd_atr': daily_atr,
                        'd_adx': daily_adx,
                        'trend_score': trend_score,
                        'v_idx': v_idx,
                        'v_dyn': v_dyn,
                        'v_eff': v_eff,
                        'v_mom': v_mom,
                        'v_hyb': v_hyb,
                        'rsi': rsi_val,
                        'rsi_angle': rsi_angle,
                        'ang_score': ang_score,
                        'ribbon_above': 1 if ribbon_above else 0
                    })
                
                current += pd.Timedelta(days=1)
        except: continue

    df = pd.DataFrame(data_points)
    
    if df.empty:
        print("Veri toplanamadı.")
        return

    # Statistics
    success = df[df['is_success'] == 1]
    fail = df[df['is_success'] == 0]
    
    metrics = ['d_atr', 'd_adx', 'trend_score', 'v_idx', 'v_dyn', 'v_mom', 'v_eff', 'v_hyb', 'rsi', 'rsi_angle', 'ang_score', 'ribbon_above']
    
    print(f"\nANALİZ SONUÇLARI ({len(df)} tetik)")
    print(f"Başarılı: {len(success)} | Başarısız: {len(fail)}\n")
    
    print(f"{'METRİK':<15} | {'BAŞARILI (Ort)':<15} | {'BAŞARISIZ (Ort)':<15} | {'FARK (%)':<10}")
    print("-" * 65)
    
    for m in metrics:
        s_mean = success[m].mean()
        f_mean = fail[m].mean()
        diff = ((s_mean - f_mean) / f_mean) * 100 if f_mean != 0 else 0
        
        print(f"{m:<15} | {s_mean:<15.2f} | {f_mean:<15.2f} | {diff:+.1f}%")

if __name__ == "__main__":
    run_factor_analysis()
