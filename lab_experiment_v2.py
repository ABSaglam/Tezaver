
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
    path = Path("coin_cells/ADAUSDT/data/history_15m.parquet")
    if not path.exists():
        print(f"File not found: {path}")
        return

    print("LOADING DATA...")
    df = pd.read_parquet(path)
    
    # Normalize Time
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
        
    df = df.sort_values('open_time').reset_index(drop=True)

    # 1. Base Indicators (RSI & Delta)
    print("CALCULATING BASE INDICATORS...")
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
    df['rsi_delta'] = df['rsi'] - df['rsi_ema']
    
    # 2. Advanced Indicators (The Deep Dive)
    # A. Volume Ratio (vs 50-bar Avg)
    df['vol_ma50'] = df['volume'].rolling(50).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma50']
    
    # B. Trend (Price vs MA200)
    df['ma200'] = df['close'].rolling(200).mean()
    df['trend_score'] = (df['close'] - df['ma200']) / df['ma200'] * 100 # % distance form MA200
    
    # C. Volatility (Bollinger Width)
    rolling_mean = df['close'].rolling(20).mean()
    rolling_std = df['close'].rolling(20).std()
    df['bb_width'] = (rolling_std * 2) / rolling_mean * 100

    # 3. Filter Cohort: RSI > 70 AND Delta < 5 (Our "Smart Entry" Group)
    df['rsi_prev'] = df['rsi'].shift(1)
    # Signal: Crosses 70
    condition_cross = (df['rsi'] > 70) & (df['rsi_prev'] <= 70)
    # Filter: Low Delta
    condition_delta = df['rsi_delta'] < 5
    
    df['cohort_signal'] = condition_cross & condition_delta
    
    cohort = df[df['cohort_signal']].copy()
    print(f"COHORT SIZE: {len(cohort)} candidates (RSI>70 & Delta<5)")

    if cohort.empty:
        print("No candidates found.")
        return

    # 4. Measure Outcome
    results = []
    for idx, row in cohort.iterrows():
        # Look ahead
        future = df.iloc[idx+1 : idx+33] # next 32 bars
        if future.empty: continue
        
        entry_price = row['close']
        max_price = future['close'].max()
        gain_pct = (max_price - entry_price) / entry_price * 100
        is_success = gain_pct > 3.0
        
        results.append({
            "gain_pct": gain_pct,
            "success": is_success,
            "vol_ratio": row['vol_ratio'],
            "trend_score": row['trend_score'],
            "bb_width": row['bb_width']
        })
        
    res_df = pd.DataFrame(results)
    
    # 5. The Verdict
    print("\n" + "="*60)
    print("🔬 DEEP DIVE REPORT: What makes a 'Low Delta' winner?")
    print("="*60)
    
    success_group = res_df[res_df['success']]
    fail_group = res_df[~res_df['success']]
    
    print(f"Global Cohort Win Rate: {len(success_group)/len(res_df)*100:.1f}% ({len(success_group)}/{len(res_df)})")
    
    print("\n--- FACTOR ANALYSIS (Winners vs Losers) ---")
    print(f"{'METRIC':<15} | {'WINNER AVG':<12} | {'LOSER AVG':<12} | {'DIFF'}")
    print("-" * 55)
    
    metrics = {
        'vol_ratio': "Volume Surge (x times avg)",
        'trend_score': "Distance from MA200 (%)",
        'bb_width': "Bollinger Width (Volatility)"
    }
    
    for m, desc in metrics.items():
        s_avg = success_group[m].mean()
        f_avg = fail_group[m].mean()
        diff = s_avg - f_avg
        print(f"{m:<15} | {s_avg:<12.2f} | {f_avg:<12.2f} | {diff:+.2f}")
        
    print("-" * 55)
    
    # 6. Test Combined Filter
    # Let's verify if Volume helps?
    print("\n--- HYPOTHESIS TEST: Volume > 1.5x ? ---")
    
    high_vol = res_df[res_df['vol_ratio'] > 1.5]
    win_rate_vol = len(high_vol[high_vol['success']]) / len(high_vol) * 100 if len(high_vol) > 0 else 0
    
    print(f"Original Win Rate: {len(success_group)/len(res_df)*100:.1f}%")
    print(f"With Volume > 1.5x Filter: {win_rate_vol:.1f}% (Count: {len(high_vol)})")

    # Let's verify Trend?
    print("\n--- HYPOTHESIS TEST: Trend > 0 (Above MA200) ? ---")
    bull_trend = res_df[res_df['trend_score'] > 0]
    win_rate_bull = len(bull_trend[bull_trend['success']]) / len(bull_trend) * 100 if len(bull_trend) > 0 else 0
    print(f"With Price > MA200 Filter: {win_rate_bull:.1f}% (Count: {len(bull_trend)})")

if __name__ == "__main__":
    run_experiment()
