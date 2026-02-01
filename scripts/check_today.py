import pandas as pd
import numpy as np
import os

COIN_CELLS_DIR = 'coin_cells'
signals = []
total_checked = 0

for symbol in os.listdir(COIN_CELLS_DIR):
    path = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path): continue
    
    total_checked += 1
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Bugünün verisi (1 Şubat)
    today = df[df.index >= '2026-02-01']
    if today.empty: continue
    
    # RSI EMA + Ribbons (Basitleştirilmiş tetik hesabı)
    delta = df['close'].diff()
    alpha = 1/11
    gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    
    all_above = pd.Series(True, index=df.index)
    for p in [20, 25, 30, 35, 40, 45, 50, 55]:
        rib = df['rsi_ema'].ewm(span=p, adjust=False).mean()
        all_above &= (df['rsi_ema'] > rib)
    
    # Bugün içinde herhangi bir tetik var mı?
    today_triggers = all_above[all_above.index >= '2026-02-01']
    if today_triggers.any():
        signals.append((symbol, today_triggers.sum()))

print(f"Total Symbols Checked: {total_checked}")
print(f"Total Symbols with ANY Signal Today: {len(signals)}")
if signals:
    print("Sample signals:", signals[:10])
