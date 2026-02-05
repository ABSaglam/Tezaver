import pandas as pd
import numpy as np
import os
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"

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
    if is_daily:
        df['atr_p'] = (tr.rolling(14).mean() / df['close']) * 100
    return df

def check_trend_ok(row):
    return (row['rsi_ema'] > row['rib_max'])

def debug_filters():
    print("🏛️ DEBUG: FILTER CHECK")
    current_date = pd.Timestamp(START_DATE)
    
    # Check BTC
    btc_p = f"{COIN_CELLS_DIR}/BTCUSDT/data/history_1d.parquet"
    btc_df = get_indicators(pd.read_parquet(btc_p).set_index(pd.to_datetime(pd.read_parquet(btc_p)['timestamp'], unit='ms')), is_daily=True)
    btc_row = btc_df[btc_df.index < current_date].tail(1)
    if not btc_row.empty:
        btc_ok = check_trend_ok(btc_row.iloc[0])
        print(f"BTC OK: {btc_ok} (RSI: {btc_row.iloc[0]['rsi_ema']:.1f}, RibMax: {btc_row.iloc[0]['rib_max']:.1f})")
    else:
        print("BTC Data Empty!")
        return

    symbols = ["SOLUSDT", "ETHUSDT", "HOLOUSD", "BROCCOLI714USDT"] # Sample
    for symbol in symbols:
        p1d = f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet"
        if not os.path.exists(p1d):
            print(f"{symbol} 1d not found")
            continue
            
        df_d = get_indicators(pd.read_parquet(p1d).set_index(pd.to_datetime(pd.read_parquet(p1d)['timestamp'], unit='ms')), is_daily=True)
        d_history = df_d[df_d.index < current_date].tail(2)
        if len(d_history) < 2:
            print(f"{symbol} history not enough")
            continue
            
        d_row, d_prev = d_history.iloc[1], d_history.iloc[0]
        d_ok = check_trend_ok(d_row)
        atr_p = d_row['atr_p']
        
        dahi_w_bypass = (d_prev['rsi_ema'] > d_prev['rib_max']) and \
                         (d_row['rsi_ema'] > 50) and \
                         (d_row['rsi_ema'] > d_prev['rsi_ema'])
                         
        print(f"{symbol} | DayOK: {d_ok} | ATR: {atr_p:.1f} | Bypass: {dahi_w_bypass}")
        print(f"  Details: RSI {d_row['rsi_ema']:.1f}, PrevRSI {d_prev['rsi_ema']:.1f}, RibMax {d_row['rib_max']:.1f}")

if __name__ == "__main__":
    debug_filters()
