"""
Enhanced Coin Character Analysis
=================================
More sophisticated character classification with 6 distinct types.
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
        return 'HEAVY', diamond_count
    elif diamond_count <= 5:
        return 'MEDIUM', diamond_count
    else:
        return 'FEATHER', diamond_count

def calculate_btc_correlation(df, btc_df):
    """Calculate correlation with BTC."""
    try:
        # Align timestamps
        df = df.set_index('timestamp')
        btc_df = btc_df.set_index('timestamp')
        
        # Merge on common timestamps
        merged = df[['close']].join(btc_df[['close']], how='inner', rsuffix='_btc')
        
        if len(merged) < 30:
            return 0.0
        
        # Calculate correlation
        correlation = merged['close'].corr(merged['close_btc'])
        return correlation if not pd.isna(correlation) else 0.0
    except:
        return 0.0

def get_enhanced_character(symbol):
    """Enhanced character classification with 6 types."""
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        btc_path = coin_cell_paths.get_history_file('BTCUSDT', '1d')
        
        if not path_1d.exists() or not btc_path.exists():
            return 'UNKNOWN', {}
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        btc_df = pd.read_parquet(btc_path).sort_values('timestamp')
        
        if len(df) < 50:
            return 'UNKNOWN', {}
        
        # === METRICS ===
        
        # 1. Wick ratio (Assassin indicator)
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['wick_ratio'] = ((df['range'] - df['body']) / df['range'] * 100).fillna(0)
        avg_wick_ratio = df['wick_ratio'].mean()
        
        # 2. Trend persistence (Knight indicator)
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['trend'] = (df['close'] > df['ema20']).astype(int)
        trend_groups = (df['trend'] != df['trend'].shift()).cumsum()
        trend_durations = df.groupby(trend_groups).size()
        avg_trend_duration = trend_durations.mean()
        
        # 3. BTC correlation (Surfer indicator)
        btc_corr = calculate_btc_correlation(df.copy(), btc_df.copy())
        
        # 4. Volume efficiency (Actor vs others)
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['price_change'] = abs(df['close'].pct_change() * 100)
        df['vol_efficiency'] = df['price_change'] / (df['volume'] / df['volume_ma'].shift(1) + 0.001)
        vol_efficiency = df['vol_efficiency'].replace([np.inf, -np.inf], 0).mean()
        
        # 5. Consolidation vs Movement (Sage indicator)
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        low_vol_periods = (df['atr'] < df['atr'].mean() * 0.5).sum()
        consolidation_ratio = low_vol_periods / len(df)
        
        # 6. Explosivity (Rocket indicator)
        df['returns'] = df['close'].pct_change()
        big_moves = (abs(df['returns']) > 0.05).sum()  # >5% daily moves
        explosivity = big_moves / len(df)
        
        metrics = {
            'wick_ratio': avg_wick_ratio,
            'trend_duration': avg_trend_duration,
            'btc_corr': btc_corr,
            'vol_efficiency': vol_efficiency,
            'consolidation_ratio': consolidation_ratio,
            'explosivity': explosivity
        }
        
        # === CHARACTER CLASSIFICATION ===
        
        # Priority order (most specific first)
        
        # 1. ASSASSIN (High wick ratio)
        if avg_wick_ratio > 70:
            return 'ASSASSIN', metrics
        
        # 2. SAGE (High consolidation + explosive moves)
        if consolidation_ratio > 0.6 and explosivity > 0.15:
            return 'SAGE', metrics
        
        # 3. SURFER (High BTC correlation)
        if btc_corr > 0.75:
            return 'SURFER', metrics
        
        # 4. ACTOR (Low volume efficiency - много шума, мало движения)
        if vol_efficiency < 0.5:
            return 'ACTOR', metrics
        
        # 5. KNIGHT (Long trend duration + medium wick)
        if avg_trend_duration > 10 and avg_wick_ratio < 60:
            return 'KNIGHT', metrics
        
        # 6. ROCKET (High explosivity + short trends)
        if explosivity > 0.2:
            return 'ROCKET', metrics
        
        # Default: KNIGHT if stable, ROCKET otherwise
        if avg_trend_duration > 7:
            return 'KNIGHT', metrics
        else:
            return 'ROCKET', metrics
            
    except Exception as e:
        return 'UNKNOWN', {}

def analyze_all_coins_enhanced():
    print("=" * 80)
    print("🧬 ENHANCED COIN CHARACTER ANALYSIS (6 Types)")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    results = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(DEFAULT_COINS)} analyzed...")
        
        weight_class, diamond_count = get_weight_class(symbol)
        character, metrics = get_enhanced_character(symbol)
        
        result = {
            'symbol': symbol,
            'weight_class': weight_class,
            'diamond_count': diamond_count,
            'character': character
        }
        result.update(metrics)
        results.append(result)
    
    df = pd.DataFrame(results)
    
    # Save
    output_file = coin_cell_paths.get_library_root() / "coin_characters_enhanced.csv"
    df.to_csv(output_file, index=False)
    
    # Statistics
    print("\n" + "=" * 80)
    print("📊 ENHANCED ANALYSIS RESULTS")
    print("=" * 80)
    
    print("\n🎭 CHARACTER DISTRIBUTION:")
    char_order = ['KNIGHT', 'ROCKET', 'SURFER', 'ASSASSIN', 'SAGE', 'ACTOR', 'UNKNOWN']
    for char in char_order:
        count = len(df[df['character'] == char])
        pct = count / len(df) * 100
        if count > 0:
            print(f"   {char:10s}: {count:3d} coins ({pct:5.1f}%)")
    
    print("\n🏋️ WEIGHT CLASS DISTRIBUTION:")
    for wc in ['HEAVY', 'MEDIUM', 'FEATHER']:
        count = len(df[df['weight_class'] == wc])
        pct = count / len(df) * 100
        print(f"   {wc:10s}: {count:3d} ({pct:5.1f}%)")
    
    print("\n🎯 TOP COMBINATIONS FOR AYAŞ TÜNELİ:")
    
    # Best: Feather + Knight
    feather_knights = df[(df['weight_class'] == 'FEATHER') & (df['character'] == 'KNIGHT')]
    print(f"\n✅ FEATHER + KNIGHT: {len(feather_knights)} coins (Diamond Hunters)")
    if len(feather_knights) > 0:
        top10 = feather_knights.nlargest(10, 'diamond_count')['symbol'].tolist()
        print(f"   Top 10: {', '.join(top10)}")
    
    # Good: Feather + Surfer
    feather_surfers = df[(df['weight_class'] == 'FEATHER') & (df['character'] == 'SURFER')]
    print(f"\n🏄 FEATHER + SURFER: {len(feather_surfers)} coins (Momentum Riders)")
    
    # Risky: Feather + Rocket
    feather_rockets = df[(df['weight_class'] == 'FEATHER') & (df['character'] == 'ROCKET')]
    print(f"\n🚀 FEATHER + ROCKET: {len(feather_rockets)} coins (High Risk/Reward)")
    
    # Avoid
    assassins = df[df['character'] == 'ASSASSIN']
    print(f"\n⚠️ ASSASSINS (All weights): {len(assassins)} coins (AVOID)")
    
    actors = df[df['character'] == 'ACTOR']
    print(f"\n🎭 ACTORS: {len(actors)} coins (Low efficiency, SKIP)")
    
    print("\n" + "=" * 80)
    print(f"✅ Enhanced Analysis Complete")
    print(f"Results: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    analyze_all_coins_enhanced()
