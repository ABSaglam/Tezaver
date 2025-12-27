
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

    # 1. Indicators
    print("CALCULATING INDICATORS...")
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
    df['rsi_delta'] = df['rsi'] - df['rsi_ema']
    
    # Trend (Price vs MA200)
    df['ma200'] = df['close'].rolling(200).mean()
    df['trend_score'] = (df['close'] - df['ma200']) / df['ma200'] * 100 
    
    # Volatility (Bollinger Width)
    rolling_mean = df['close'].rolling(20).mean()
    rolling_std = df['close'].rolling(20).std()
    df['bb_width'] = (rolling_std * 2) / rolling_mean * 100

    # 2. DEFINING THE "GOLDEN COMBO"
    # Base Signal: RSI Crosses 70
    df['rsi_prev'] = df['rsi'].shift(1)
    cond_cross = (df['rsi'] > 70) & (df['rsi_prev'] <= 70)
    
    # Filters
    cond_delta = df['rsi_delta'] < 5          # "Smart Entry" (Not Overextended)
    cond_trend = df['trend_score'] > 10       # "Strong Uptrend" (>10% above MA200)
    cond_vol   = df['bb_width'] > 4           # "Active Market" (>4% width)
    
    df['combo_signal'] = cond_cross & cond_delta & cond_trend & cond_vol
    
    trades = df[df['combo_signal']].copy()
    print(f"FOUND {len(trades)} TRADES matching Golden Combo criteria.")

    if trades.empty:
        print("No trades found. Strategy too strict?")
        return

    # 3. Simulate Trades
    results = []
    holding_bars = 32  # 8 Hours fixed exit for stats
    
    for idx, row in trades.iterrows():
        entry_price = row['close']
        
        # Look ahead
        future = df.iloc[idx+1 : idx+1+holding_bars]
        if future.empty: continue
        
        # Metrics
        max_price = future['close'].max()  # Best case (Peak)
        exit_price = future['close'].iloc[-1] # Fixed Exit (8h later)
        min_price = future['close'].min() # Max Drawdown
        
        # Gains
        gain_at_peak = (max_price - entry_price) / entry_price * 100
        gain_at_exit = (exit_price - entry_price) / entry_price * 100
        drawdown = (min_price - entry_price) / entry_price * 100
        
        is_success = gain_at_peak > 3.0
        
        results.append({
            "gain_peak": gain_at_peak,
            "gain_exit": gain_at_exit,
            "drawdown": drawdown,
            "success": is_success
        })
        
    res_df = pd.DataFrame(results)
    
    # 4. Final Report
    print("\n" + "="*60)
    print("💰 GOLDEN COMBO RESULTS (ADAUSDT 15m)")
    print(f"Filters: RSI>70 | Delta<5 | Trend>10% | BB>4%")
    print("="*60)
    
    total_trades = len(res_df)
    winners = res_df[res_df['success']]
    win_rate = len(winners) / total_trades * 100
    
    avg_peak_gain = res_df['gain_peak'].mean()
    avg_exit_gain = res_df['gain_exit'].mean()
    max_dd_avg = res_df['drawdown'].mean()
    
    print(f"TOTAL TRADES:       {total_trades}")
    print(f"WIN RATE (>3%):     {win_rate:.1f}%")
    print("-" * 30)
    print(f"AVG GAIN (at Peak): {avg_peak_gain:.2f}%")
    print(f"AVG GAIN (Fixed 8h):{avg_exit_gain:.2f}%")
    print(f"AVG DRAWDOWN:       {max_dd_avg:.2f}%")
    
    # Cumulative Return Simulation (Simple Compounding)
    initial_capital = 1000
    capital = initial_capital
    for r in res_df['gain_exit']:
        capital *= (1 + r/100)
    
    print("-" * 30)
    print(f"HYPOTHETICAL GROWTH: ${initial_capital} -> ${capital:.0f} (x{capital/initial_capital:.1f})")

if __name__ == "__main__":
    run_experiment()
