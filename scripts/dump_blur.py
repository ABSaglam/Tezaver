
import pandas as pd
import numpy as np
import os

def dump_vals():
    symbol = "BLURUSDT"
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path): return

    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df.sort_index(inplace=True)
    
    # RSI(11) - Wilder's
    delta = df['close'].diff()
    alpha = 1 / 11
    gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    rsi = 100 - (100 / (1 + (gain / loss)))
    
    # RSI-based MA (EMA 11)
    rsi_ma = rsi.ewm(span=11, adjust=False).mean()
    
    # Ribbon (EMA 20 of rsi_ma)
    ribbon = rsi_ma.ewm(span=20, adjust=False).mean()
    
    print(f"📊 BLUR Biyopsisi (18:00 - 19:00 UTC) [Timezone: UTC+3 için 21:00-22:00]")
    print("-" * 80)
    print(f"{'Time (UTC)':<20} {'Close':<10} {'RSI':<10} {'RSI-MA':<10} {'Rib-20':<10}")
    
    targets = rsi.loc["2026-01-14 18:00":"2026-01-14 19:00"]
    for ts in targets.index:
        print(f"{str(ts):<20} {df.loc[ts, 'close']:<10.4f} {rsi.loc[ts]:<10.2f} {rsi_ma.loc[ts]:<10.2f} {ribbon.loc[ts]:<10.2f}")

    print("-" * 80)
    print("Sizin Beklentiniz (TV SAATİ 21:30 -> UTC 18:30):")
    print("21:00 (18:00 UTC) -> 53.57")
    print("21:15 (18:15 UTC) -> 53.24")
    print("21:30 (18:30 UTC) -> 53.14")

if __name__ == "__main__":
    dump_vals()
