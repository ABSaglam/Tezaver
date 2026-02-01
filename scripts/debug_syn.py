import pandas as pd
import numpy as np
import sys
import os

# Add scripts to path
sys.path.insert(0, '/Users/alisaglam/TezaverMac/scripts')
from portakal_sikacagi import apply_portakal_sikacagi
import math

SYMBOL = "SYNUSDT"
DATE = "2026-01-30"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def load_clean(path):
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

print(f"DEBUGGING {SYMBOL} for {DATE}")

# Load Data
df_15m = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_15m.parquet")
df_1d = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_1d.parquet")
df_4h = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_4h.parquet")
df_1h = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_1h.parquet")

# Calculate Indicators (Copied from reporter)
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

# Trigger Logic
ribbon_max = df_15m[rsi_ribbon_cols].max(axis=1)
rsi_ema = df_15m['rsi_ema']
cond_now = rsi_ema > ribbon_max
triggers = (cond_now) & (~cond_now.shift(1).fillna(False))

# Filter for the specific date
target_day = pd.Timestamp(DATE).normalize()
day_mask = (df_15m.index.normalize() == target_day)
day_indices = np.where(day_mask)[0]

print(f"\nTotal bars for {DATE}: {len(day_indices)}")

triggers_found = []

# Daily Context
df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
df_1d['atr14'] = d_tr.rolling(window=14).mean()
df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100

# ADX
plus_dm = df_1d['high'].diff()
minus_dm = -df_1d['low'].diff()
plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
tr14 = d_tr.rolling(window=14).sum()
plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14)
minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14)
dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
df_1d['adx14'] = dx.rolling(window=14).mean()

d_atr = df_1d['atr_pct'].asof(target_day)
d_adx = df_1d['adx14'].asof(target_day)

print(f"Daily ATR (asof): {d_atr:.2f}, Daily ADX (asof): {d_adx:.2f}")

# Test Report Logic
try:
    daily_atr_val = df_1d.loc[df_1d.index.normalize() == target_day, 'atr_pct']
    if not daily_atr_val.empty:
        rep_d_atr = daily_atr_val.values[0]
    else:
        rep_d_atr = 0.0
except: rep_d_atr = 0.0

try:
    daily_adx_val = df_1d.loc[df_1d.index.normalize() == target_day, 'adx14']
    if not daily_adx_val.empty:
        rep_d_adx = daily_adx_val.values[0]
    else:
        rep_d_adx = 0.0
except: rep_d_adx = 0.0

print(f"Daily ATR (Report Logic): {rep_d_atr:.2f}")
print(f"Daily ADX (Report Logic): {rep_d_adx:.2f}")

if rep_d_atr < 4.0:
    print("⚠️ WARNING: Report Logic would FILTER OUT this coin due to d_atr < 4")
if rep_d_adx < 0.1: # Assuming 0 means failed lookup
    print("⚠️ WARNING: Report Logic failed to find ADX value")

# Continue with debug using REPORT LOGIC values to see if it fails
d_atr = rep_d_atr
d_adx = rep_d_adx

# 4H/1H EMAs
df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()

# ATR Calc for 15m
tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
df_15m['atr100'] = tr.rolling(window=100).mean()
df_15m['atr21'] = tr.rolling(window=21).mean()
df_15m['tr'] = tr

for i in day_indices:
    if triggers.iloc[i]:
        time_str = df_15m.index[i].strftime("%H:%M")
        print(f"\n--- TRIGGER FOUND AT {time_str} ---")
        
        # Prepare context for Portakal Check
        trig_time = df_15m.index[i]
        
        cutoff_4h = trig_time - pd.Timedelta(hours=4)
        last_4h = df_4h[df_4h.index <= cutoff_4h]
        t4 = 1 if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else 0
        
        cutoff_1h = trig_time - pd.Timedelta(hours=1)
        last_1h = df_1h[df_1h.index <= cutoff_1h]
        t1 = 1 if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else 0
        
        trend_str = f"{t4}{t1}"
        trend_score = t4 + t1
        
        print(f"Trend: {trend_str} (4H:{t4}, 1H:{t1})")
        
        val_20 = df_15m['rsi_rib_20'].values[i]
        val_55 = df_15m['rsi_rib_55'].values[i]
        ribbon_above = val_20 > val_55
        curr_v = val_20 if ribbon_above else val_55
        
        if curr_v < 30: pos_color = "black"
        elif curr_v < 50: pos_color = "red"
        elif curr_v < 60: pos_color = "yellow"
        elif curr_v < 70: pos_color = "green"
        else: pos_color = "orange"
        
        print(f"POS Color: {pos_color}")
        
        # Calculate Peak
        # Simple lookahead
        search_limit = i + 22
        if i + 1 < len(df_15m):
            val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
            peak_p = val_slice.max() if len(val_slice) > 0 else df_15m['close'].values[i]
        else:
            peak_p = df_15m['close'].values[i]
            
        peak_curr = ((peak_p / df_15m['close'].values[i]) - 1) * 100
        print(f"Actual Peak: {peak_curr:.2f}%")
        
        # Metrics
        v_idx = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr100'].values[i] or 0.001)) * 3.33)
        print(f"v_index: {v_idx:.2f}")

        # Construct Trigger Dict
        trig_dict = {
            'time': time_str,
            'd_atr': d_atr, 'd_adx': d_adx,
            'trend_str': trend_str, 'trend_score': trend_score,
            'pos': pos_color, 'ribbon_above': ribbon_above,
            'ang_score': 0, 'rsi': df_15m['rsi'].values[i],
            'v_idx': v_idx,
            'peak_pct': peak_curr # For context, though filter doesn't use it to decide
        }
        
        # Test Portakal
        df_test = pd.DataFrame([trig_dict])
        df_res = apply_portakal_sikacagi(df_test, verbose=True)
        
        if df_res.empty:
            print("❌ FILTERED OUT by Portakal Sıkacağı")
        else:
            print("✅ PASSED Filter")

