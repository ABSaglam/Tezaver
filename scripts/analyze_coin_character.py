"""
Coin Character & Weight Class Analysis
======================================
Analyzes each coin's behavior pattern (Character) and potential (Weight Class).
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def get_weight_class(symbol):
    """Determine weight class based on Diamond rally history."""
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT COUNT(*) FROM rallies WHERE symbol = '{symbol}' AND tier = 'DIAMOND'"
    diamond_count = pd.read_sql_query(query, conn).iloc[0, 0]
    conn.close()
    
    if diamond_count == 0:
        return 'HEAVY', diamond_count  # Never did Diamond
    elif diamond_count <= 5:
        return 'MEDIUM', diamond_count  # Rare Diamond
    else:
        return 'FEATHER', diamond_count  # Frequent Diamond

def get_character(symbol):
    """Determine character based on trading behavior."""
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return 'UNKNOWN', {}
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        if len(df) < 50:
            return 'UNKNOWN', {}
        
        # Calculate metrics
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['wick_ratio'] = ((df['range'] - df['body']) / df['range'] * 100).fillna(0)
        
        # EMA for trend analysis
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['trend'] = (df['close'] > df['ema20']).astype(int)
        
        # Metrics
        avg_wick_ratio = df['wick_ratio'].mean()
        
        # Trend persistence (how long trends last)
        trend_groups = (df['trend'] != df['trend'].shift()).cumsum()
        trend_durations = df.groupby(trend_groups).size()
        avg_trend_duration = trend_durations.mean()
        
        # Volatility
        df['returns'] = df['close'].pct_change()
        volatility = df['returns'].std() * 100
        
        metrics = {
            'wick_ratio': avg_wick_ratio,
            'trend_duration': avg_trend_duration,
            'volatility': volatility
        }
        
        # Character classification
        if avg_wick_ratio > 65:  # High wick = trappy
            return 'ASSASSIN', metrics  # İğneci/Suikastçi
        elif avg_trend_duration > 8:  # Long trends = loyal
            return 'KNIGHT', metrics  # Şövalye
        else:  # Explosive/quick
            return 'ROCKET', metrics  # Roketçi
            
    except Exception as e:
        return 'UNKNOWN', {}

def analyze_all_coins():
    print("=" * 80)
    print("🧬 COIN CHARACTER & WEIGHT CLASS ANALYSIS")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    results = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(DEFAULT_COINS)} analyzed...")
        
        weight_class, diamond_count = get_weight_class(symbol)
        character, metrics = get_character(symbol)
        
        results.append({
            'symbol': symbol,
            'weight_class': weight_class,
            'diamond_count': diamond_count,
            'character': character,
            'wick_ratio': metrics.get('wick_ratio', 0),
            'trend_duration': metrics.get('trend_duration', 0),
            'volatility': metrics.get('volatility', 0)
        })
    
    df = pd.DataFrame(results)
    
    # Save results
    output_file = coin_cell_paths.get_library_root() / "coin_characters.csv"
    df.to_csv(output_file, index=False)
    
    # Statistics
    print("\n" + "=" * 80)
    print("📊 ANALYSIS RESULTS")
    print("=" * 80)
    
    print("\n🏋️ WEIGHT CLASS DISTRIBUTION:")
    for wc in ['HEAVY', 'MEDIUM', 'FEATHER']:
        count = len(df[df['weight_class'] == wc])
        pct = count / len(df) * 100
        avg_diamonds = df[df['weight_class'] == wc]['diamond_count'].mean()
        print(f"   {wc:10s}: {count:3d} coins ({pct:5.1f}%) | Avg Diamonds: {avg_diamonds:.1f}")
    
    print("\n🎭 CHARACTER DISTRIBUTION:")
    for char in ['KNIGHT', 'ROCKET', 'ASSASSIN', 'UNKNOWN']:
        count = len(df[df['character'] == char])
        pct = count / len(df) * 100
        print(f"   {char:10s}: {count:3d} coins ({pct:5.1f}%)")
    
    print("\n🎯 RECOMMENDED COMBINATIONS:")
    
    # Best for Ayaş Tüneli
    feather_knights = df[(df['weight_class'] == 'FEATHER') & (df['character'] == 'KNIGHT')]
    print(f"\n✅ FEATHER + KNIGHT (Diamond Hunters): {len(feather_knights)} coins")
    if len(feather_knights) > 0:
        top5 = feather_knights.nlargest(5, 'diamond_count')['symbol'].tolist()
        print(f"   Top 5: {', '.join(top5)}")
    
    # Safe trading
    medium_knights = df[(df['weight_class'] == 'MEDIUM') & (df['character'] == 'KNIGHT')]
    print(f"\n🛡️ MEDIUM + KNIGHT (Safe Traders): {len(medium_knights)} coins")
    
    # Avoid
    assassins = df[df['character'] == 'ASSASSIN']
    print(f"\n⚠️ ASSASSINS (Trappy, Avoid): {len(assassins)} coins")
    
    print("\n" + "=" * 80)
    print(f"✅ Analysis Complete - Results saved to: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    analyze_all_coins()
