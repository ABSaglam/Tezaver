import pandas as pd
import numpy as np
import os
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
OUTPUT_CSV = "/Users/alisaglam/TezaverMac/rally_dna_audit_results.csv"

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/11, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
    rs = gain / (loss + 0.0001)
    return 100 - (100 / (1 + rs))

def get_indicators(df, is_daily=False):
    if df.empty: return df
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    rib_periods = [20, 25, 30, 35, 40, 45, 50, 55]
    for p in rib_periods:
        df[f'rsi_rib_{p}'] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
    df['rib_max'] = df[[f'rsi_rib_{p}' for p in [20, 55]]].max(axis=1)
    tr = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['tr'] = tr
    if not is_daily:
        df['vol_ma50'] = df['volume'].rolling(window=50).mean()
        df['v_mom'] = df['volume'] / df['vol_ma50'].replace(0, 1)
    return df

def audit_rallies():
    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    rally_events = []

    for symbol in symbols:
        print(f"Auditing Rallies for {symbol}...")
        try:
            p15m, p1d, p1w = [f"{COIN_CELLS_DIR}/{symbol}/data/history_{tf}.parquet" for tf in ['15m', '1d', '1w']]
            if not all(os.path.exists(p) for p in [p15m, p1d, p1w]): continue
            
            df_d = get_indicators(pd.read_parquet(p1d).set_index(pd.to_datetime(pd.read_parquet(p1d)['timestamp'], unit='ms')), is_daily=True)
            df_w = get_indicators(pd.read_parquet(p1w).set_index(pd.to_datetime(pd.read_parquet(p1w)['timestamp'], unit='ms')), is_daily=True)
            df_15m = get_indicators(pd.read_parquet(p15m).set_index(pd.to_datetime(pd.read_parquet(p15m)['timestamp'], unit='ms')))
            
            # Find all 15m trigger candidates
            cond_up = (df_15m['rsi_ema'] > df_15m['rib_max'])
            trigs = (cond_up) & (~cond_up.shift(1).fillna(False))
            
            for ti in np.where(trigs)[0]:
                ts = df_15m.index[ti]
                if ts < pd.to_datetime(START_DATE) or ts > pd.to_datetime(END_DATE): continue
                
                # Check W/D Confirmation at Trigger Time
                d_row = df_d[df_d.index < ts.replace(hour=0, minute=0, second=0)].tail(1)
                w_row = df_w[df_w.index < ts.replace(hour=0, minute=0, second=0)].tail(1)
                
                if d_row.empty or w_row.empty: continue
                
                # GATE 1: W/D Vise check
                if not ((d_row.iloc[0]['rsi_ema'] > d_row.iloc[0]['rib_max']) and (w_row.iloc[0]['rsi_ema'] > w_row.iloc[0]['rib_max'])):
                    continue

                # Now evaluate this specific 15m trigger
                idx_f = df_15m.index.get_loc(ts)
                future = df_15m.iloc[idx_f + 1 : idx_f + 100] # Look further
                if future.empty: continue
                
                entry_p = df_15m.iloc[idx_f]['close']
                peak_p = future['high'].max()
                max_g = ((peak_p / entry_p) - 1) * 100
                
                # We only care about success (Tier Silver+) to find the "Winning DNA"
                if max_g >= 10.0:
                    # Surgical Metrics at Trigger (T-0)
                    rsi_now = df_15m.iloc[idx_f]['rsi_ema']
                    rsi_prev = df_15m.iloc[idx_f - 1]['rsi_ema']
                    ang = math.degrees(math.atan(rsi_now - rsi_prev))
                    v_mom = df_15m.iloc[idx_f]['v_mom']
                    dist_to_rib = rsi_now - df_15m.iloc[idx_f]['rib_max']
                    
                    # Pre-Trigger Context (Last 4 bars)
                    past_4 = df_15m.iloc[idx_f-4:idx_f]
                    vol_avg_past = past_4['v_mom'].mean()
                    
                    rally_events.append({
                        'symbol': symbol, 'time': ts, 'peak': max_g,
                        'rsi_val': rsi_now, 'rsi_ang': ang,
                        'v_mom': v_mom, 'vol_avg_past': vol_avg_past,
                        'dist_rib': dist_to_rib,
                        'tr_p': (df_15m.iloc[idx_f]['tr'] / entry_p) * 100
                    })
        except: continue
            
    pd.DataFrame(rally_events).to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Rally DNA Audit completed: {OUTPUT_CSV}")

if __name__ == "__main__":
    audit_rallies()
