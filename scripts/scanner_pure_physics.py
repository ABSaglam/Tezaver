import pandas as pd
import numpy as np
import glob
import os
from datetime import datetime

# CONFIG
TARGET_COIN = "AUCTIONUSDT"
DATA_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
REPORT_FILE = "/Users/alisaglam/TezaverMac/PURE_PHYSICS_REPORT.md"

def calculate_rsi(series, period=11):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_scan():
    print(f"🚀 STARTING PURE PHYSICS SCAN (RSI 11 + RIBBON) for {TARGET_COIN}...")
    
    # 1. Load Data
    files = glob.glob(f"{DATA_DIR}/{TARGET_COIN}/data/history_15m.parquet")
    if not files:
        print("❌ Data file not found!")
        return

    df = pd.read_parquet(files[0])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()

    # 2. Indicators (The 'Physics')
    df['vol_ma'] = df['volume'].rolling(21).mean()
    df['rsi'] = calculate_rsi(df['close'], 11)
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    
    # Ribbon (20-55 on RSI EMA)
    ribbon_cols = []
    for p in [20, 25, 30, 35, 40, 45, 50, 55]:
        col = f'r{p}'
        df[col] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
        ribbon_cols.append(col)
    
    df['ribbon_max'] = df[ribbon_cols].max(axis=1)
    df['ribbon_min'] = df[ribbon_cols].min(axis=1)

    # 3. Trigger Logic (Sequential)
    # A. Volume Prep: Vol > 1.5x MA
    df['vol_ready'] = df['volume'] > (df['vol_ma'] * 1.5)
    
    # B. Breakout: RSI_EMA crosses above Ribbon Max
    # Logic: Current RSI_EMA > Max Ribbon AND Previous RSI_EMA <= Previous Max Ribbon
    df['breakout'] = (df['rsi_ema'] > df['ribbon_max']) & (df['rsi_ema'].shift(1) <= df['ribbon_max'].shift(1))
    
    # C. Sequence: Breakout NOW + Volume Ready in last 3 bars
    # We look at a 3-bar window ending at current bar
    df['vol_window'] = df['vol_ready'].astype(int).rolling(window=3).max()
    
    df['trigger'] = df['breakout'] & (df['vol_window'] == 1)
    
    # 4. Filter & Report
    # Focus on 2026 data as requested
    start_date = pd.Timestamp("2026-01-01").tz_localize("UTC")
    results = df[df.index >= start_date].copy()
    triggered = results[results['trigger'] == True]
    
    if triggered.empty:
        print("❄️ No signals found.")
        return

    print(f"🔥 Found {len(triggered)} signals.")
    
    with open(REPORT_FILE, 'w') as f:
        f.write(f"# PURE PHYSICS REPORT: {TARGET_COIN}\n")
        f.write("Logic: RSI(11) Ribbon Breakout + Volume(1.5x) Sequence\n\n")
        f.write("| DATE | TIME | PRICE | RSI | R-EMA | RIB-MAX | VOL | RATIO | GAIN (24H) |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        
        for idx, row in triggered.iterrows():
            # Calculate simple 24h forward gain for validation
            future = results.loc[idx:].iloc[1:96] # Approx 24h
            if not future.empty:
                max_price = future['high'].max()
                gain = ((max_price - row['close']) / row['close']) * 100
            else:
                gain = 0
            
            vol_ratio = row['volume'] / row['vol_ma'] if row['vol_ma'] > 0 else 0
            
            line = f"| {idx.strftime('%d %b')} | {idx.strftime('%H:%M')} | {row['close']:.4f} | {row['rsi']:.1f} | {row['rsi_ema']:.1f} | {row['ribbon_max']:.1f} | {int(row['volume'])} | {vol_ratio:.1f}x | **+{gain:.1f}%** |"
            f.write(line + "\n")
            print(line)

    print(f"✅ Report saved: {REPORT_FILE}")

if __name__ == "__main__":
    run_scan()
