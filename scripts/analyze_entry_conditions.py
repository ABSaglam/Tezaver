"""
Coin Classification by Entry Conditions
========================================
Analyze what conditions precede rallies for each coin,
then group coins that respond to similar conditions.
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def get_pre_rally_conditions(symbol, start_time):
    """Get indicator values before a rally starts."""
    try:
        # Load 1d data for indicators
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return None
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        # Find the bar just before rally
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        pre_rally = df[df['timestamp'] < start_ts].tail(5)  # Last 5 bars before rally
        
        if len(pre_rally) < 3:
            return None
        
        last_bar = pre_rally.iloc[-1]
        
        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'], 14)
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        df['vol_ma'] = df['volume'].rolling(20).mean()
        
        # Get values at rally start
        idx = df[df['timestamp'] < start_ts].index[-1]
        
        rsi = df.loc[idx, 'rsi'] if 'rsi' in df.columns else 50
        atr = df.loc[idx, 'atr'] if 'atr' in df.columns else 5
        
        # Trend: price vs EMAs
        close = df.loc[idx, 'close']
        ema20 = df.loc[idx, 'ema20']
        ema50 = df.loc[idx, 'ema50']
        
        above_ema20 = 1 if close > ema20 else 0
        above_ema50 = 1 if close > ema50 else 0
        ema_cross = 1 if ema20 > ema50 else 0
        
        # Volume
        vol = df.loc[idx, 'volume']
        vol_ma = df.loc[idx, 'vol_ma']
        vol_ratio = vol / vol_ma if vol_ma > 0 else 1
        
        # RSI zones
        rsi_oversold = 1 if rsi < 30 else 0
        rsi_overbought = 1 if rsi > 70 else 0
        rsi_neutral = 1 if 30 <= rsi <= 70 else 0
        
        return {
            'rsi': rsi,
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': rsi_overbought,
            'rsi_neutral': rsi_neutral,
            'atr': atr,
            'above_ema20': above_ema20,
            'above_ema50': above_ema50,
            'ema_cross_bullish': ema_cross,
            'vol_ratio': vol_ratio,
            'high_volume': 1 if vol_ratio > 1.5 else 0
        }
        
    except Exception as e:
        return None

def calculate_rsi(prices, period=14):
    """Calculate RSI."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_coin_entry_conditions():
    print("=" * 80)
    print("🎯 COİN GİRİŞ KOŞULLARI ANALİZİ")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load all DSG rallies
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT symbol, raw_data, tier FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Toplam ralli: {len(df_rallies)}")
    
    # Sample for speed (analyze every 10th rally)
    sample_size = min(10000, len(df_rallies))
    df_sample = df_rallies.sample(n=sample_size, random_state=42)
    
    print(f"Örnek boyutu: {sample_size}")
    
    results = []
    
    for i, row in df_sample.iterrows():
        if (len(results) + 1) % 1000 == 0:
            print(f"İlerleme: {len(results)+1}/{sample_size}")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        if raw_data is None:
            continue
            
        symbol = raw_data.get('symbol', row.get('symbol', ''))
        start_time = raw_data.get('start_time')
        
        if not start_time:
            continue
        
        conditions = get_pre_rally_conditions(symbol, start_time)
        
        if conditions:
            conditions['symbol'] = symbol
            conditions['tier'] = row['tier']
            results.append(conditions)
    
    df = pd.DataFrame(results)
    
    if df.empty:
        print("❌ Veri yok")
        return
    
    print(f"\n✅ {len(df)} ralli koşulu analiz edildi")
    
    # Aggregate by symbol
    print("\n" + "=" * 80)
    print("📊 COİN BAZINDA GİRİŞ KOŞULLARI PROFİLİ")
    print("=" * 80)
    
    coin_profiles = df.groupby('symbol').agg({
        'rsi': 'mean',
        'rsi_oversold': 'mean',  # % of rallies starting from oversold
        'rsi_overbought': 'mean',
        'rsi_neutral': 'mean',
        'atr': 'mean',
        'above_ema20': 'mean',  # % of rallies starting above EMA20
        'above_ema50': 'mean',
        'ema_cross_bullish': 'mean',
        'vol_ratio': 'mean',
        'high_volume': 'mean'
    }).round(2)
    
    # Add rally count
    rally_counts = df.groupby('symbol').size()
    coin_profiles['rally_count'] = rally_counts
    
    # Save
    output_file = coin_cell_paths.get_library_root() / "coin_entry_profiles.csv"
    coin_profiles.to_csv(output_file)
    
    # Find patterns
    print("\n📊 Baskın Giriş Koşullarına Göre Gruplar:")
    
    # Group 1: Oversold starters (RSI < 30)
    oversold_coins = coin_profiles[coin_profiles['rsi_oversold'] > 0.3]
    print(f"\n🔴 OVERSOLD BAŞLAYANLAR ({len(oversold_coins)} coin):")
    print(f"   Rallilerin >30%'u RSI<30'da başlıyor")
    top5 = oversold_coins.nlargest(5, 'rsi_oversold')
    for sym, row in top5.iterrows():
        print(f"   {sym:15s}: {row['rsi_oversold']*100:.0f}% oversold, {row['rally_count']:.0f} ralli")
    
    # Group 2: Trend followers (above EMA20)
    trend_coins = coin_profiles[coin_profiles['above_ema20'] > 0.6]
    print(f"\n📈 TREND TAKİPÇİLERİ ({len(trend_coins)} coin):")
    print(f"   Rallilerin >60%'ı EMA20 üzerinde başlıyor")
    top5 = trend_coins.nlargest(5, 'above_ema20')
    for sym, row in top5.iterrows():
        print(f"   {sym:15s}: {row['above_ema20']*100:.0f}% trend, {row['rally_count']:.0f} ralli")
    
    # Group 3: Volume driven
    volume_coins = coin_profiles[coin_profiles['high_volume'] > 0.4]
    print(f"\n📊 HACİM ODAKLI ({len(volume_coins)} coin):")
    print(f"   Rallilerin >40%'ı yüksek hacimle başlıyor")
    top5 = volume_coins.nlargest(5, 'high_volume')
    for sym, row in top5.iterrows():
        print(f"   {sym:15s}: {row['high_volume']*100:.0f}% high vol, {row['rally_count']:.0f} ralli")
    
    # Group 4: Momentum (RSI > 50 + above EMA)
    momentum_coins = coin_profiles[(coin_profiles['rsi'] > 50) & (coin_profiles['above_ema20'] > 0.5)]
    print(f"\n🚀 MOMENTUM ({len(momentum_coins)} coin):")
    print(f"   Ortalama RSI>50, çoğu EMA20 üzerinde başlıyor")
    
    print("\n" + "=" * 80)
    print(f"✅ Profiller kaydedildi: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    analyze_coin_entry_conditions()
