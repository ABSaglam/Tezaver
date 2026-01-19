"""
Coin-Specific Diamond Autopsy
==============================
Deep individual analysis of top Diamond producers.
Goal: Understand each coin's unique Diamond DNA - no general rules.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def autopsy_coin(symbol, timeframe='1d'):
    """Complete autopsy of a single coin."""
    print(f"\n{'='*80}")
    print(f"🔬 {symbol} - COMPLETE AUTOPSY")
    print(f"{'='*80}")
    
    # Get ALL rallies for this coin (all time)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT tier, event_time, raw_data FROM rallies 
        WHERE symbol = '{symbol}'
        ORDER BY event_time
    """)
    all_rallies = cursor.fetchall()
    conn.close()
    
    if not all_rallies:
        print(f"❌ No rally data for {symbol}")
        return None
    
    # Categorize
    diamonds = []
    golds = []
    silvers = []
    bronzes = []
    
    for tier, event_time, raw_data in all_rallies:
        raw = json.loads(raw_data)
        rally = {'tier': tier, 'event_time': event_time, 'start_time': raw['start_time'], 'gain': raw['gain']}
        
        if tier == 'DIAMOND':
            diamonds.append(rally)
        elif tier == 'GOLD':
            golds.append(rally)
        elif tier == 'SILVER':
            silvers.append(rally)
        elif tier == 'BRONZE':
            bronzes.append(rally)
    
    print(f"\n📊 RALLY HISTORY (ALL TIME)")
    print(f"💎 Diamond: {len(diamonds)}")
    print(f"🥇 Gold: {len(golds)}")
    print(f"🥈 Silver: {len(silvers)}")
    print(f"🟡 Bronze: {len(bronzes)}")
    
    # Load price data
    path = coin_cell_paths.get_history_file(symbol, timeframe)
    if not path.exists():
        print(f"❌ No price data for {symbol}")
        return None
    
    df = pd.read_parquet(path).sort_values('timestamp')
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Calculate ALL indicators
    df['rsi'] = calculate_rsi(df['close'])
    df['rsi_ema9'] = df['rsi'].ewm(span=9).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    
    macd, macd_signal, hist = calculate_macd(df['close'])
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = hist
    df['macd_rising'] = hist > hist.shift(1)
    
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['atr'] = (df['high'] - df['low']) / df['close'] * 100
    
    df['price_1d'] = df['close'].pct_change(1) * 100
    df['price_3d'] = df['close'].pct_change(3) * 100
    df['price_7d'] = df['close'].pct_change(7) * 100
    df['price_30d'] = df['close'].pct_change(30) * 100
    
    # Analyze Diamond pre-conditions
    print(f"\n💎 DIAMOND ANALYSIS ({len(diamonds)} rallies)")
    print("-" * 80)
    
    diamond_conditions = []
    
    for dia in diamonds:
        start = pd.to_datetime(dia['start_time'])
        sig_date = start - pd.Timedelta(days=1)
        
        sig_rows = df[df['datetime'].dt.date == sig_date.date()]
        if sig_rows.empty:
            continue
        
        sig = sig_rows.iloc[0]
        sig_idx = sig_rows.index[0]
        
        # Get 7-day window before
        if sig_idx >= 7:
            week = df.iloc[sig_idx-7:sig_idx+1]
            
            condition = {
                'date': dia['event_time'][:10],
                'gain': dia['gain'],
                'rsi': sig['rsi'],
                'rsi_7d_min': week['rsi'].min(),
                'rsi_7d_max': week['rsi'].max(),
                'rsi_7d_change': week['rsi'].iloc[-1] - week['rsi'].iloc[0],
                'atr': sig['atr'],
                'atr_7d_avg': week['atr'].mean(),
                'vol': sig['vol_ratio'],
                'vol_7d_max': week['vol_ratio'].max(),
                'macd_hist': sig['macd_hist'],
                'price_7d': sig['price_7d'],
                'price_30d': sig['price_30d'],
                'ema9_above_21': sig['ema9'] > sig['ema21'],
                'ema9_above_50': sig['ema9'] > sig['ema50'],
                'close_vs_ema9': (sig['close'] - sig['ema9']) / sig['ema9'] * 100
            }
            
            diamond_conditions.append(condition)
    
    if diamond_conditions:
        df_dia = pd.DataFrame(diamond_conditions)
        
        print(f"\n🔑 DIAMOND PRE-CONDITIONS (n={len(df_dia)})")
        print(f"RSI: {df_dia['rsi'].mean():.1f} ± {df_dia['rsi'].std():.1f} (min:{df_dia['rsi'].min():.1f}, max:{df_dia['rsi'].max():.1f})")
        print(f"RSI 7d Range: {df_dia['rsi_7d_min'].mean():.1f} - {df_dia['rsi_7d_max'].mean():.1f}")
        print(f"RSI 7d Change: {df_dia['rsi_7d_change'].mean():+.1f}")
        print(f"ATR: {df_dia['atr'].mean():.1f}% ± {df_dia['atr'].std():.1f}%")
        print(f"Vol Ratio: {df_dia['vol'].mean():.1f}x (max: {df_dia['vol_7d_max'].mean():.1f}x)")
        print(f"MACD Hist: {df_dia['macd_hist'].mean():+.3f}")
        print(f"Price 7d: {df_dia['price_7d'].mean():+.1f}%")
        print(f"Price 30d: {df_dia['price_30d'].mean():+.1f}%")
        print(f"EMA9>21: {df_dia['ema9_above_21'].sum()}/{len(df_dia)} ({df_dia['ema9_above_21'].sum()/len(df_dia)*100:.0f}%)")
        print(f"Close vs EMA9: {df_dia['close_vs_ema9'].mean():+.1f}%")
        
        # Show individual Diamonds
        print(f"\n📋 INDIVIDUAL DIAMONDS:")
        for _, row in df_dia.iterrows():
            print(f"  {row['date']} %{row['gain']:6.1f} | RSI:{row['rsi']:5.1f} ATR:{row['atr']:5.1f}% Vol:{row['vol']:4.1f}x Price7d:{row['price_7d']:+6.1f}%")
    
    return {
        'symbol': symbol,
        'diamonds': len(diamonds),
        'golds': len(golds),
        'diamond_conditions': diamond_conditions
    }

if __name__ == "__main__":
    # Top 5 Diamond producers (from DB query)
    top_coins = ['GUNUSDT', 'BROCCOLI714USDT', 'AXSUSDT', 'QUICKUSDT', 'PEPEUSDT']
    
    results = []
    for coin in top_coins:
        result = autopsy_coin(coin)
        if result:
            results.append(result)
    
    # Save
    output_path = coin_cell_paths.get_library_root() / "coin_autopsy_report.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Autopsy complete. Saved to: {output_path}")
