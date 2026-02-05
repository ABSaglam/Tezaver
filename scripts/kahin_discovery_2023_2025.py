import pandas as pd
import numpy as np
import os
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
OUTPUT_CSV = "/Users/alisaglam/TezaverMac/kahin_discovery_results.csv"

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
    df['rib_min_all'] = df[[f'rsi_rib_{p}' for p in rib_periods]].min(axis=1)
    tr = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['tr'] = tr
    if is_daily:
        df['vol_ma50'] = df['volume'].rolling(window=50).mean()
        df['atr_p'] = (tr.rolling(14).mean() / df['close']) * 100
        df['vol_mom'] = df['volume'] / df['vol_ma50'].replace(0, 1)
    return df

def check_trend_ok(row):
    if row is None or len(row) == 0: return False
    return (row['rsi_ema'] > row['rib_max']) or (row['rib_min_all'] > 60.0)

def discover():
    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    all_dates = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
    
    samples = []
    
    # 🏛️ PRE-LOAD BTC DATA FOR CONTEXT
    btc_1d = get_indicators(pd.read_parquet(f"{COIN_CELLS_DIR}/BTCUSDT/data/history_1d.parquet").set_index(pd.to_datetime(pd.read_parquet(f"{COIN_CELLS_DIR}/BTCUSDT/data/history_1d.parquet")['timestamp'], unit='ms')), is_daily=True)
    btc_1w = get_indicators(pd.read_parquet(f"{COIN_CELLS_DIR}/BTCUSDT/data/history_1w.parquet").set_index(pd.to_datetime(pd.read_parquet(f"{COIN_CELLS_DIR}/BTCUSDT/data/history_1w.parquet")['timestamp'], unit='ms')))

    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        try:
            p15m, p1d, p1w = [f"{COIN_CELLS_DIR}/{symbol}/data/history_{tf}.parquet" for tf in ['15m', '1d', '1w']]
            if not all(os.path.exists(p) for p in [p15m, p1d, p1w]): continue
            
            df_d = get_indicators(pd.read_parquet(p1d).set_index(pd.to_datetime(pd.read_parquet(p1d)['timestamp'], unit='ms')), is_daily=True)
            df_w = get_indicators(pd.read_parquet(p1w).set_index(pd.to_datetime(pd.read_parquet(p1w)['timestamp'], unit='ms')))
            df_15m = pd.read_parquet(p15m).set_index(pd.to_datetime(pd.read_parquet(p15m)['timestamp'], unit='ms'))
            
            for current_date in all_dates:
                # 🏛️ GATE 1 CHECK (W and D at Yesterday's close)
                d_match = df_d[df_d.index < current_date].tail(1)
                w_match = df_w[df_w.index < current_date].tail(1)
                
                if d_match.empty or w_match.empty: continue
                
                d_row, w_row = d_match.iloc[0], w_match.iloc[0]
                
                if check_trend_ok(d_row) and check_trend_ok(w_row):
                    # 🏛️ GATHER FEATURES AT DAY OPEN
                    btc_d = btc_1d[btc_1d.index < current_date].tail(1).iloc[0]
                    btc_w = btc_1w[btc_1w.index < current_date].tail(1).iloc[0]
                    btc_ok = check_trend_ok(btc_d) and check_trend_ok(btc_w)
                    
                    # 🏛️ LOOK AHEAD FOR TARGET (Did it achieve Tier Bronze+ today?)
                    day_data = df_15m[(df_15m.index >= current_date) & (df_15m.index < current_date + pd.Timedelta(days=1))]
                    if day_data.empty: continue
                    
                    entry_p = day_data.iloc[0]['open']
                    max_p = day_data['high'].max()
                    peak_gain = ((max_p / entry_p) - 1) * 100
                    target = 1 if peak_gain >= 5.0 else 0
                    
                    samples.append({
                        'symbol': symbol,
                        'date': current_date,
                        'rsi_d': d_row['rsi_ema'],
                        'rsi_pos': d_row['rsi'],
                        'rsi_diff': d_row['rsi_ema'] - d_row['rib_max'],
                        'atr_p': d_row['atr_p'],
                        'vol_mom': d_row['vol_mom'],
                        'btc_ok': 1 if btc_ok else 0,
                        'peak': peak_gain,
                        'target': target
                    })
        except Exception as e:
            print(f"Error {symbol}: {e}")
            continue
            
    pd.DataFrame(samples).to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Discovery completed: {OUTPUT_CSV}")

if __name__ == "__main__":
    discover()
