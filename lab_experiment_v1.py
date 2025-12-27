
import pandas as pd
import numpy as np
from pathlib import Path
import sys

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def run_experiment():
    # 1. Load Data
    path = Path("coin_cells/ADAUSDT/data/history_15m.parquet")
    if not path.exists():
        print(f"File not found: {path}")
        return

    print("LOADING DATA...")
    df = pd.read_parquet(path)
    
    # Normalize Time Column
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        # ensure datetime
        df['open_time'] = pd.to_datetime(df['open_time']) 
        
    if 'open_time' not in df.columns:
        print("ERROR: No time column found.")
        return

    df = df.sort_values('open_time').reset_index(drop=True)
    
    # Needs 'close'
    if 'close' not in df.columns:
        print("Missing 'close' column")
        return

    # 2. Calculate Indicators
    print("CALCULATING INDICATORS...")
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
    df['rsi_delta'] = df['rsi'] - df['rsi_ema']
    
    # 3. Identify Signals (RSI Crosses 70)
    # condition: RSI > 70 and RSI_prev <= 70
    df['rsi_prev'] = df['rsi'].shift(1)
    df['signal'] = (df['rsi'] > 70) & (df['rsi_prev'] <= 70)
    
    signals = df[df['signal']].copy()
    print(f"FOUND {len(signals)} SIGNALS (RSI > 70 Cross).")
    
    # 4. Measure Outcome (Look ahead 32 bars ~ 8 hours)
    results = []
    
    for idx, row in signals.iterrows():
        entry_price = row['close']
        entry_time = row['open_time']
        
        # Future window
        future = df.iloc[idx+1 : idx+33] # next 32 bars
        if future.empty: continue
        
        max_price = future['close'].max()
        gain_pct = (max_price - entry_price) / entry_price * 100
        
        # Determine Success (Let's say > 3% is a RALLY for 15m)
        is_success = gain_pct > 3.0
        
        results.append({
            "time": entry_time,
            "rsi": row['rsi'],
            "rsi_ema": row['rsi_ema'],
            "delta": row['rsi_delta'],
            "gain_pct": gain_pct,
            "success": is_success
        })
        
    res_df = pd.DataFrame(results)
    
    if res_df.empty:
        print("No results.")
        return

    # 5. Analysis (The Verdict)
    print("\n" + "="*50)
    print("🔬 LABORATORY REPORT: ADAUSDT 15m (RSI > 70)")
    print("="*50)
    
    success_group = res_df[res_df['success']]
    fail_group = res_df[~res_df['success']]
    
    print(f"TOTAL SIGNALS: {len(res_df)}")
    print(f"SUCCESS (>3%): {len(success_group)} ({len(success_group)/len(res_df)*100:.1f}%)")
    print(f"FAILURE (<3%): {len(fail_group)} ({len(fail_group)/len(res_df)*100:.1f}%)")
    
    print("\n--- THE DIFFERENCE (ALPHA HUNT) ---")
    
    print(f"{'METRIC':<15} | {'SUCCESS AVG':<12} | {'FAILURE AVG':<12} | {'DIFF'}")
    print("-" * 55)
    
    for metric in ['rsi', 'rsi_ema', 'delta']:
        s_avg = success_group[metric].mean()
        f_avg = fail_group[metric].mean()
        diff = s_avg - f_avg
        print(f"{metric.upper():<15} | {s_avg:<12.2f} | {f_avg:<12.2f} | {diff:+.2f}")
        
    print("-" * 55)
    
    # Additional Insight: Does 'delta' help?
    # Check if high delta correlates with success
    print("\n--- DELTA DISTRIBUTION ---")
    print("Is High Delta (Distance from EMA) better?")
    
    df_high_delta = res_df[res_df['delta'] > 10]
    win_rate_high = len(df_high_delta[df_high_delta['success']]) / len(df_high_delta) * 100 if len(df_high_delta) > 0 else 0
    
    df_low_delta = res_df[res_df['delta'] < 5]
    win_rate_low = len(df_low_delta[df_low_delta['success']]) / len(df_low_delta) * 100 if len(df_low_delta) > 0 else 0
    
    print(f"If Delta > 10 (Explosive): Win Rate {win_rate_high:.1f}% (Count: {len(df_high_delta)})")
    print(f"If Delta < 5  (Gradual):   Win Rate {win_rate_low:.1f}% (Count: {len(df_low_delta)})")

if __name__ == "__main__":
    run_experiment()
