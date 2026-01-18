"""
Rally Shape Classification
===========================
Classifies each DSG rally into archetypes: Supernova, Merdiven, Grind, Spike, Breakout
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

def classify_rally_shape(symbol, start_time, end_time, gain, bars):
    """
    Classify a rally into an archetype based on its price action shape.
    
    Returns: archetype name and metrics
    """
    try:
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists():
            return 'UNKNOWN', {}
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        # Find rally window
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        end_ts = pd.to_datetime(end_time).timestamp() * 1000
        
        # Get rally data
        rally_df = df[(df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)].copy()
        
        if len(rally_df) < 3:
            return 'UNKNOWN', {}
        
        # Normalize prices to percentage gain from start
        start_price = rally_df.iloc[0]['low']
        rally_df['pct_gain'] = (rally_df['close'] - start_price) / start_price * 100
        
        total_bars = len(rally_df)
        max_gain = rally_df['pct_gain'].max()
        peak_idx = rally_df['pct_gain'].idxmax()
        peak_position = (rally_df.index.get_loc(peak_idx) + 1) / total_bars  # 0-1 where peak occurred
        
        # === METRICS ===
        
        # 1. Speed Ratio: How much of the gain happened in first 30% of time?
        first_30_pct_bars = max(1, int(total_bars * 0.3))
        first_30_gain = rally_df.iloc[:first_30_pct_bars]['pct_gain'].max()
        speed_ratio = first_30_gain / max_gain if max_gain > 0 else 0
        
        # 2. Pullback Count: How many significant pullbacks during rally?
        rally_df['rolling_high'] = rally_df['pct_gain'].cummax()
        rally_df['drawdown'] = rally_df['rolling_high'] - rally_df['pct_gain']
        significant_pullbacks = (rally_df['drawdown'] > max_gain * 0.1).sum()  # >10% of total gain
        
        # 3. Volatility during rally
        rally_df['returns'] = rally_df['close'].pct_change()
        rally_volatility = rally_df['returns'].std() * 100 if len(rally_df) > 1 else 0
        
        # 4. Pre-rally volatility (10 bars before)
        pre_start = max(0, rally_df.index[0] - 10)
        pre_df = df.iloc[pre_start:rally_df.index[0]]
        if len(pre_df) > 1:
            pre_volatility = pre_df['close'].pct_change().std() * 100
            volatility_expansion = rally_volatility / pre_volatility if pre_volatility > 0 else 1
        else:
            volatility_expansion = 1
        
        # 5. Post-peak behavior (if we have data after peak)
        post_peak_df = rally_df.loc[peak_idx:]
        if len(post_peak_df) > 2:
            post_peak_drop = (post_peak_df['pct_gain'].max() - post_peak_df['pct_gain'].iloc[-1]) / max_gain
        else:
            post_peak_drop = 0
        
        metrics = {
            'speed_ratio': round(speed_ratio, 2),
            'pullback_count': int(significant_pullbacks),
            'total_bars': total_bars,
            'peak_position': round(peak_position, 2),
            'volatility_expansion': round(volatility_expansion, 2),
            'post_peak_drop': round(post_peak_drop, 2)
        }
        
        # === CLASSIFICATION LOGIC ===
        
        # SUPERNOVA: Fast peak (first 30% of time), minimal pullbacks
        if speed_ratio > 0.7 and peak_position < 0.4 and significant_pullbacks < 2:
            return 'SUPERNOVA', metrics
        
        # SPIKE: Peak early, then significant drop
        if peak_position < 0.3 and post_peak_drop > 0.5:
            return 'SPIKE', metrics
        
        # MERDIVEN (Staircase): Multiple pullbacks, gradual climb
        if significant_pullbacks >= 3 and total_bars > 20:
            return 'MERDIVEN', metrics
        
        # BREAKOUT: Low pre-rally volatility, then expansion
        if volatility_expansion > 2.0 and speed_ratio > 0.5:
            return 'BREAKOUT', metrics
        
        # GRIND: Steady climb, few pullbacks, moderate speed
        if significant_pullbacks < 2 and speed_ratio < 0.5 and total_bars > 15:
            return 'GRIND', metrics
        
        # Default: Check if it's more explosive or gradual
        if speed_ratio > 0.5:
            return 'SUPERNOVA', metrics
        else:
            return 'GRIND', metrics
            
    except Exception as e:
        return 'UNKNOWN', {}

def run_classification():
    print("=" * 80)
    print("🎯 RALLİ ŞEKİL SINIFLANDIRMASI")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load all DSG rallies
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    total = len(df_rallies)
    print(f"\nToplam DSG Ralli: {total}\n")
    
    results = []
    
    for i, row in df_rallies.iterrows():
        if (i + 1) % 5000 == 0:
            print(f"İlerleme: {i+1}/{total} ralli analiz edildi...")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        
        symbol = raw_data.get('symbol', row.get('symbol', ''))
        start_time = raw_data.get('start_time')
        end_time = raw_data.get('end_time')
        gain = raw_data.get('gain', 0)
        bars = raw_data.get('bars', 0)
        tier = row['tier']
        
        archetype, metrics = classify_rally_shape(symbol, start_time, end_time, gain, bars)
        
        results.append({
            'symbol': symbol,
            'tier': tier,
            'archetype': archetype,
            'gain': gain,
            **metrics
        })
    
    df = pd.DataFrame(results)
    
    # Save raw results
    output_file = coin_cell_paths.get_library_root() / "rally_archetypes.csv"
    df.to_csv(output_file, index=False)
    
    # === PHASE 1: Archetype Distribution ===
    print("\n" + "=" * 80)
    print("📊 AŞAMA 1: RALLİ ARKETİP DAĞILIMI")
    print("=" * 80)
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        tier_df = df[df['tier'] == tier]
        if tier_df.empty:
            continue
        
        print(f"\n{'─' * 60}")
        print(f"🔹 {tier} ({len(tier_df)} ralli)")
        print(f"{'─' * 60}")
        
        archetype_counts = tier_df['archetype'].value_counts()
        for arch, count in archetype_counts.items():
            pct = count / len(tier_df) * 100
            avg_gain = tier_df[tier_df['archetype'] == arch]['gain'].mean()
            avg_bars = tier_df[tier_df['archetype'] == arch]['total_bars'].mean()
            print(f"   {arch:12s}: {count:5d} ({pct:5.1f}%) | Ort. Kazanç: {avg_gain:5.1f}% | Ort. Süre: {avg_bars:5.1f} bar")
    
    # === PHASE 2: Coin Behavior ===
    print("\n" + "=" * 80)
    print("📊 AŞAMA 2: COİN DAVRANIŞ ANALİZİ")
    print("=" * 80)
    
    # Get unique coins and their archetype distribution
    coin_archetypes = df.groupby(['symbol', 'archetype']).size().unstack(fill_value=0)
    coin_archetypes['total'] = coin_archetypes.sum(axis=1)
    coin_archetypes['dominant'] = coin_archetypes.drop('total', axis=1).idxmax(axis=1)
    
    # Calculate dominant archetype percentage
    for arch in ['SUPERNOVA', 'MERDIVEN', 'GRIND', 'SPIKE', 'BREAKOUT']:
        if arch in coin_archetypes.columns:
            coin_archetypes[f'{arch}_pct'] = coin_archetypes[arch] / coin_archetypes['total'] * 100
    
    # Save coin analysis
    coin_output = coin_cell_paths.get_library_root() / "coin_rally_behavior.csv"
    coin_archetypes.to_csv(coin_output)
    
    print("\n🔹 Baskın Arketipe Göre Coin Dağılımı:")
    dominant_counts = coin_archetypes['dominant'].value_counts()
    for arch, count in dominant_counts.items():
        print(f"   {arch:12s}: {count:3d} coin")
        
        # Top coins for this archetype
        arch_coins = coin_archetypes[coin_archetypes['dominant'] == arch].nlargest(5, 'total')
        top_coins = arch_coins.index.tolist()[:5]
        print(f"      Top 5: {', '.join(top_coins)}")
    
    print("\n" + "=" * 80)
    print(f"✅ Analiz Tamamlandı")
    print(f"Ralli verileri: {output_file}")
    print(f"Coin davranışları: {coin_output}")
    print("=" * 80)

if __name__ == "__main__":
    run_classification()
