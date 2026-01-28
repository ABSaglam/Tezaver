import pandas as pd
import numpy as np
import os

def crisis_diagnostic():
    symbol = "ZROUSDT"
    print(f"--- CRISIS DIAGNOSTIC: {symbol} ---")
    
    # Load same way
    df_15m = pd.read_parquet(f"coin_cells/{symbol}/data/history_15m.parquet")
    df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m.set_index('dt', inplace=True)
    
    current = pd.Timestamp("2025-12-01")
    full_15m = df_15m[df_15m.index <= current + pd.Timedelta(days=1)].copy()
    
    # 1. RSI (11)
    delta = full_15m['close'].diff()
    alpha = 1 / 11
    avg_gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    avg_loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    full_15m['rsi'] = 100 - (100 / (1 + (avg_gain / avg_loss)))

    # 3. RSI-Ribbon
    ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
    rsi_ribbon_cols = []
    for p in ribbon_periods:
        col_name = f'rsi_ribbon_{p}'
        full_15m[col_name] = full_15m['rsi'].ewm(span=p, adjust=False).mean()
        rsi_ribbon_cols.append(col_name)

    target_day_data = full_15m[full_15m.index.normalize() == current]
    rsi_vals = full_15m['rsi'].values
    rsi_ribbon_matrix = full_15m[rsi_ribbon_cols].values
    
    day_start_idx = full_15m.index.get_indexer([target_day_data.index[0]])[0]
    day_end_idx = full_15m.index.get_indexer([target_day_data.index[-1]])[0]
    
    target_time_str = "20:45"
    found = False
    
    print(f"Scanning from idx {day_start_idx} to {day_end_idx}...")
    
    for i in range(day_start_idx, day_end_idx + 1):
        if i < 7: continue 
        time_str = full_15m.index[i].strftime("%H:%M")
        
        if time_str == target_time_str:
            found = True
            rsi_curr = rsi_vals[i]
            rsi_prev = rsi_vals[i-1]
            
            # TRIGGER CONDITION
            trigger_hits = rsi_prev <= 70 and rsi_curr > 70
            
            # ALIGNMENT CHECK
            rsi_rib_row = rsi_ribbon_matrix[i]
            is_rsi_aligned = all(rsi_rib_row[j] > rsi_rib_row[j+1] for j in range(len(rsi_rib_row)-1))
            
            print(f"FOUND 20:45 | RSI Prev: {rsi_prev:.2f} | RSI Curr: {rsi_curr:.2f}")
            print(f"TRIGGER HITS: {trigger_hits}")
            print(f"RSI VALUES: {[round(v, 2) for v in rsi_rib_row]}")
            print(f"IS ALIGNED: {is_rsi_aligned}")
            
            if is_rsi_aligned:
                rsi_ema20_curr = rsi_rib_row[0]
                rsi_ema20_prev = rsi_ribbon_matrix[i-1][0]
                denom = rsi_ema20_prev if abs(rsi_ema20_prev) > 0.001 else 0.001
                slope = ((rsi_ema20_curr / denom) - 1) * 100
                print(f"SLOPE CALCULATED: %{slope:.2f}")

    if not found:
        print("CRITICAL: 20:45 not found in date range.")

if __name__ == "__main__":
    crisis_diagnostic()
