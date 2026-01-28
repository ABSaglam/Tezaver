
import pandas as pd
import numpy as np
import os

def find_sequence():
    symbol = "BLURUSDT"
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path): return

    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df.sort_index(inplace=True)
    
    # User values sequence
    target_seq = [53.57, 53.24, 53.14]

    # Calculate indicators
    for rsi_p in [11, 14]:
        delta = df['close'].diff()
        alpha = 1 / rsi_p
        gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
        rsi = 100 - (100 / (1 + (gain / loss)))
        
        for ma_p in [11]:
            rsi_ma = rsi.ewm(span=ma_p, adjust=False).mean()
            
            for rib_p in [20]:
                ribbon = rsi_ma.ewm(span=rib_p, adjust=False).mean()
                
                # Scan through 2026-01-14
                day_data = ribbon.loc["2026-01-14"]
                for i in range(2, len(day_data)):
                    v1, v2, v3 = day_data.iloc[i-2], day_data.iloc[i-1], day_data.iloc[i]
                    if abs(v3 - 53.14) < 0.5:
                        print(f"Potential Match at {day_data.index[i]} UTC")
                        print(f"Vals: {v1:.2f}, {v2:.2f}, {v3:.2f}")
                        print(f"Target: 53.57, 53.24, 53.14")
                        print(f"Params: RSI={rsi_p}, MA={ma_p}, Rib={rib_p}")
                        print("-" * 20)

if __name__ == "__main__":
    find_sequence()
