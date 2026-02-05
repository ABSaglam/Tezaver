import pandas as pd
import numpy as np
import os
import json

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SOUL_PATH = "/Users/alisaglam/TezaverMac/ignition_soul_manifest.json"

with open(SOUL_PATH, "r") as f:
    SOUL = json.load(f)

def get_threshold(symbol):
    return SOUL.get(symbol, 5.0)

def analyze_sequence(df, i, symbol):
    if i + 2 >= len(df): return False
    t0, t1, t2 = df.iloc[i], df.iloc[i+1], df.iloc[i+2]
    v_ratio0 = t0['volume'] / (t0['vol_ma50'] or 0.001)
    if v_ratio0 < get_threshold(symbol): return False
    v_ratio1 = t1['volume'] / (t1['vol_ma50'] or 0.001)
    if v_ratio1 < 2.0: return False
    if t1['close'] < t0['open']: return False
    if t2['rsi'] < t0['rsi']: return False
    if t2['rsi_ema'] <= t1['rsi_ema']: return False
    return True

def run_count(year_target):
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if d.endswith("USDT")]
    count = 0
    for symbol in symbols:
        p = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
        if not os.path.exists(p): continue
        df = pd.read_parquet(p)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df = df[df.index.year == year_target]
        if df.empty: continue
        df['vol_ma50'] = df['volume'].rolling(50).mean()
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/11, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
        for i in range(50, len(df)-2):
            if analyze_sequence(df, i, symbol):
                count += 1
    return count

if __name__ == "__main__":
    c2025 = run_count(2025)
    c2026 = run_count(2026)
    print(f"2025 (TAM YIL) Sinyal Sayisi: {c2025}")
    print(f"2026 (01 OCAK - 03 SUBAT) Sinyal Sayisi: {c2026}")
