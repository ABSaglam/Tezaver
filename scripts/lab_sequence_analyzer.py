import pandas as pd
import numpy as np
import os
import math

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def analyze_sequence(symbol, target_time):
    path_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path_15m): return None
    
    df = pd.read_parquet(path_15m)
    if 'datetime' in df.columns:
        df.set_index('datetime', inplace=True)
        df.index = pd.to_datetime(df.index)
    
    # Calculate indicators
    df['vol_ma'] = df['volume'].rolling(50).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
    
    for p in [20, 55]:
        df[f'ribbon_{p}'] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
        
    # Find T0 index
    try:
        t0_idx = df.index.get_loc(target_time)
    except:
        return None
        
    sequence = []
    # Take T-1, T0, T+1, T+2
    for offset in [-1, 0, 1, 2]:
        idx = t0_idx + offset
        if idx < 0 or idx >= len(df): continue
        
        row = df.iloc[idx]
        prev_row = df.iloc[idx-1] if idx > 0 else row
        
        seq_step = {
            'step': f"T{offset}" if offset != 0 else "T0",
            'time': df.index[idx].strftime("%H:%M"),
            'price': row['close'],
            'vol_ratio': row['volume'] / row['vol_ma'] if row['vol_ma'] > 0 else 0,
            'rsi': row['rsi'],
            'rsi_ema': row['rsi_ema'],
            'ribbon_gap': row['ribbon_20'] - row['ribbon_55'],
            'body_pct': abs(row['close'] - row['open']) / (row['high'] - row['low'] + 0.0001) * 100,
            'candle_pct': (row['close'] / row['open'] - 1) * 100
        }
        sequence.append(seq_step)
        
    return sequence

if __name__ == "__main__":
    masters = [
        ("HYPERUSDT", "2025-07-08 16:30:00+00:00"),
        ("TNSRUSDT", "2025-11-18 12:00:00+00:00"),
        ("DEXEUSDT", "2025-10-10 21:15:00+00:00"),
        ("GIGGLEUSDT", "2025-11-04 09:45:00+00:00"),
        ("SPKUSDT", "2025-07-21 16:15:00+00:00")
    ]
    
    for sym, t_str in masters:
        print(f"\n--- FORENSIC: {sym} at {t_str} ---")
        seq = analyze_sequence(sym, pd.Timestamp(t_str))
        if seq:
            df_seq = pd.DataFrame(seq)
            print(df_seq[['step', 'time', 'vol_ratio', 'rsi', 'rsi_ema', 'ribbon_gap', 'candle_pct']].to_string())
        else:
            print("Sequence not found.")
