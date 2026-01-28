
import pandas as pd
import numpy as np
import os

def find_match():
    symbol = "BLURUSDT"
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path): return

    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep='last')]

    # Targets
    t_2100 = pd.Timestamp("2026-01-14 21:00:00")
    t_2115 = pd.Timestamp("2026-01-14 21:15:00")
    t_2130 = pd.Timestamp("2026-01-14 21:30:00")

    # User values
    u_vals = [53.57, 53.24, 53.14]

    print("🔍 Searching for match...")
    
    # Try different RSI periods
    for rsi_p in [11, 14]:
        delta = df['close'].diff()
        # Wilder's RSI (TradingView default)
        alpha = 1 / rsi_p
        gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
        rsi = 100 - (100 / (1 + (gain / loss)))
        
        # Try different RSI-MA periods (The source for the ribbon)
        for ma_p in [11, 14]:
            rsi_ma = rsi.ewm(span=ma_p, adjust=False).mean()
            
            # Try different Ribbon periods
            for rib_p in [20, 21]:
                ribbon = rsi_ma.ewm(span=rib_p, adjust=False).mean()
                
                v1 = ribbon.loc[t_2100] if t_2100 in ribbon.index else 0
                v2 = ribbon.loc[t_2115] if t_2115 in ribbon.index else 0
                v3 = ribbon.loc[t_2130] if t_2130 in ribbon.index else 0
                
                # Check match (within small tolerance)
                if abs(v3 - 53.14) < 1.0:
                    print(f"MATCH (CLOSE): RSI={rsi_p}, MA={ma_p}, Rib={rib_p}")
                    print(f"Vals: {v1:.2f}, {v2:.2f}, {v3:.2f}")
                    print(f"Target: 53.57, 53.24, 53.14")
                    print("-" * 20)

if __name__ == "__main__":
    find_match()
