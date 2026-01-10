"""
Backtest Daily Radar System
============================
Tests the 1D + 4H filter across all historical data.
For each day, applies the filter and tracks outcomes.
"""

import pandas as pd
import numpy as np
from tezaver.core import config, coin_cell_paths
from datetime import timedelta


def calculate_daily_metrics(df, idx):
    """Calculate daily structure metrics at a specific index (day)."""
    if idx < 20 or idx >= len(df):
        return None
        
    try:
        # Slice up to (and including) idx
        df_slice = df.iloc[:idx+1].copy()
        
        # ATR%
        df_slice['tr'] = np.maximum(
            df_slice['high'] - df_slice['low'],
            np.maximum(
                abs(df_slice['high'] - df_slice['close'].shift(1)),
                abs(df_slice['low'] - df_slice['close'].shift(1))
            )
        )
        atr = df_slice['tr'].rolling(14).mean().iloc[-1]
        atr_pct = (atr / df_slice['close'].iloc[-1]) * 100
        
        # Position within 5-day range
        high_5d = df_slice['high'].tail(5).max()
        low_5d = df_slice['low'].tail(5).min()
        range_5d = high_5d - low_5d
        if range_5d > 0:
            midpoint_pct = ((df_slice['close'].iloc[-1] - low_5d) / range_5d) * 100
        else:
            midpoint_pct = 50.0
            
        # Green days
        df_slice['green'] = df_slice['close'] > df_slice['open']
        green_days = df_slice['green'].tail(3).sum()
        
        return {
            'atr_pct': atr_pct,
            'midpoint_pct': midpoint_pct,
            'green_days': green_days
        }
    except:
        return None


def calculate_4h_momentum(df_4h, target_date):
    """Calculate 4H momentum at a specific date."""
    if df_4h is None or len(df_4h) < 50:
        return None
        
    try:
        # Standardize datetime
        if 'datetime' in df_4h.columns:
            df_4h['ts'] = pd.to_datetime(df_4h['datetime'], utc=True)
        elif 'timestamp' in df_4h.columns:
            df_4h['ts'] = pd.to_datetime(df_4h['timestamp'], unit='ms', utc=True)
        else:
            return None
            
        # Filter to data up to target date
        df_slice = df_4h[df_4h['ts'].dt.date <= target_date].tail(30).copy()
        if len(df_slice) < 10:
            return None
            
        # RSI
        delta = df_slice['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        rs = up.ewm(com=13, adjust=False).mean() / down.ewm(com=13, adjust=False).mean()
        df_slice['rsi'] = 100 - (100 / (1 + rs))
        
        rsi_now = df_slice['rsi'].iloc[-1]
        rsi_6_ago = df_slice['rsi'].iloc[-7] if len(df_slice) >= 7 else df_slice['rsi'].iloc[0]
        rsi_rising = rsi_now > rsi_6_ago
        
        # MACD
        ema12 = df_slice['close'].ewm(span=12, adjust=False).mean()
        ema26 = df_slice['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df_slice['macd_hist'] = macd_line - signal_line
        
        macd_rising = df_slice['macd_hist'].iloc[-1] > df_slice['macd_hist'].iloc[-4] if len(df_slice) >= 4 else False
        
        # Green bars
        df_slice['green'] = df_slice['close'] > df_slice['open']
        green_bars = df_slice['green'].tail(3).sum()
        
        return {
            'rsi': rsi_now,
            'rsi_rising': rsi_rising,
            'macd_rising': macd_rising,
            'green_bars': green_bars
        }
    except:
        return None


def passes_filters(daily, momentum):
    """Check if both filters pass."""
    if daily is None or momentum is None:
        return False
    # Daily filter
    if daily['atr_pct'] < 2.0:
        return False
    if daily['midpoint_pct'] < 40:
        return False
    if daily['green_days'] < 1:
        return False
    # Momentum filter
    if momentum['rsi'] < 45:
        return False
    if not (momentum['rsi_rising'] or momentum['macd_rising']):
        return False
    if momentum['green_bars'] < 1:
        return False
    return True


def run_backtest():
    print("=== DAILY RADAR BACKTEST ===")
    print("Testing: 1D Structure + 4H Momentum Filter")
    print("Outcome: What happens in the next 7 days?")
    
    coins = config.DEFAULT_COINS
    
    all_outcomes = []
    
    for c_idx, symbol in enumerate(coins):
        if c_idx % 10 == 0:
            print(f"Processing {c_idx}/{len(coins)} coins...", end='\r')
            
        try:
            # Load daily data
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            if not path_1d.exists():
                continue
            df_1d = pd.read_parquet(path_1d)
            if len(df_1d) < 50:
                continue
                
            # Standardize date
            if 'datetime' in df_1d.columns:
                df_1d['date'] = pd.to_datetime(df_1d['datetime']).dt.date
            elif 'timestamp' in df_1d.columns:
                df_1d['date'] = pd.to_datetime(df_1d['timestamp'], unit='ms').dt.date
            else:
                continue
                
            # Load 4H data
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            df_4h = pd.read_parquet(path_4h) if path_4h.exists() else None
            
            # Iterate through each day (skip first 30, last 7)
            for day_idx in range(30, len(df_1d) - 7):
                target_date = df_1d.iloc[day_idx]['date']
                
                # Calculate metrics as of that day
                daily = calculate_daily_metrics(df_1d, day_idx)
                momentum = calculate_4h_momentum(df_4h, target_date) if df_4h is not None else None
                
                if not passes_filters(daily, momentum):
                    continue
                    
                # PASSED FILTER - Track Outcome
                entry_price = df_1d.iloc[day_idx]['close']
                
                # Future 7 days
                future_slice = df_1d.iloc[day_idx+1 : day_idx+8]
                if len(future_slice) < 1:
                    continue
                    
                max_price = future_slice['high'].max()
                min_price = future_slice['low'].min()
                final_price = future_slice.iloc[-1]['close']
                
                max_gain = (max_price - entry_price) / entry_price * 100
                max_draw = (min_price - entry_price) / entry_price * 100
                final_return = (final_price - entry_price) / entry_price * 100
                
                all_outcomes.append({
                    'symbol': symbol,
                    'date': target_date,
                    'max_gain': max_gain,
                    'max_draw': max_draw,
                    'final_return': final_return
                })
                
        except Exception as e:
            continue
    
    print("\n\n=== BACKTEST RESULTS ===")
    
    if not all_outcomes:
        print("No signals found!")
        return
        
    df_out = pd.DataFrame(all_outcomes)
    
    total = len(df_out)
    print(f"Total Signals (Filter Passed Days): {total}")
    
    # Win Rates
    win_5 = len(df_out[df_out['max_gain'] >= 5]) / total * 100
    win_10 = len(df_out[df_out['max_gain'] >= 10]) / total * 100
    win_20 = len(df_out[df_out['max_gain'] >= 20]) / total * 100
    
    loss_5 = len(df_out[df_out['max_draw'] <= -5]) / total * 100
    loss_10 = len(df_out[df_out['max_draw'] <= -10]) / total * 100
    
    avg_max_gain = df_out['max_gain'].mean()
    avg_final = df_out['final_return'].mean()
    avg_draw = df_out['max_draw'].mean()
    
    print(f"\n--- WIN RATES (7 Days) ---")
    print(f"+5% Hit Rate:  {win_5:.1f}%")
    print(f"+10% Hit Rate: {win_10:.1f}%")
    print(f"+20% Hit Rate: {win_20:.1f}%")
    
    print(f"\n--- RISK ---")
    print(f"-5% Drawdown Rate:  {loss_5:.1f}%")
    print(f"-10% Drawdown Rate: {loss_10:.1f}%")
    
    print(f"\n--- AVERAGES ---")
    print(f"Avg Max Gain:    +{avg_max_gain:.2f}%")
    print(f"Avg Final Return: {avg_final:+.2f}%")
    print(f"Avg Max Drawdown: {avg_draw:.2f}%")
    
    # Quality Check: Is it better than random?
    print("\n--- VERDICT ---")
    if avg_final > 0 and win_10 > 30:
        print("✅ SYSTEM WORKS! Filter provides edge.")
    elif avg_final > 0:
        print("⚠️ Marginally Profitable. Consider tightening filters.")
    else:
        print("❌ SYSTEM FAILS. Filter does not predict outcomes.")


if __name__ == "__main__":
    run_backtest()
