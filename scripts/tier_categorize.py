"""
Trading-Optimized Coin Tier System
===================================
Categorizes coins into practical tiers for trading strategies.
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

def categorize_coin_tier(symbol):
    """Categorize a single coin into tier system."""
    try:
        # Load data
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return None
        
        df_1d = pd.read_parquet(path_1d).sort_values('timestamp')
        
        # === METRICS ===
        # 1. Liquidity (average daily volume)
        avg_volume = df_1d['volume'].mean()
        
        # 2. Volatility (daily ATR%)
        df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100
        avg_atr = df_1d['atr'].mean()
        
        # 3. Rally data from DB
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT * FROM rallies WHERE symbol = '{symbol}' AND tier IN ('DIAMOND', 'GOLD', 'SILVER')"
        df_rallies = pd.read_sql_query(query, conn)
        conn.close()
        
        dsg_count = len(df_rallies)
        diamond_count = len(df_rallies[df_rallies['tier'] == 'DIAMOND'])
        
        # 4. Clean ratio (from anomaly detection - assume we have this data)
        # For now, estimate: if anomaly data not available, use 90% default
        clean_ratio = 0.90  # Default assumption
        
        # === TIER ASSIGNMENT (SIMPLE VOLUME-BASED) ===
        
        # TIER A: Ultra High Liquidity (>5B)
        if avg_volume > 5_000_000_000:
            return {'symbol': symbol, 'tier': 'A', 'volume': avg_volume, 'atr': avg_atr, 
                    'dsg_count': dsg_count, 'diamond_count': diamond_count}
        
        # TIER B: High Liquidity (1B-5B)
        if avg_volume > 1_000_000_000:
            return {'symbol': symbol, 'tier': 'B', 'volume': avg_volume, 'atr': avg_atr, 
                    'dsg_count': dsg_count, 'diamond_count': diamond_count}
        
        # TIER C: Medium Liquidity (100M-1B)
        if avg_volume > 100_000_000:
            return {'symbol': symbol, 'tier': 'C', 'volume': avg_volume, 'atr': avg_atr, 
                    'dsg_count': dsg_count, 'diamond_count': diamond_count}
        
        # TIER D: Low Liquidity (10M-100M)
        if avg_volume > 10_000_000:
            return {'symbol': symbol, 'tier': 'D', 'volume': avg_volume, 'atr': avg_atr, 
                    'dsg_count': dsg_count, 'diamond_count': diamond_count}
        
        # TIER X: Very Low Liquidity (<10M)
        return {'symbol': symbol, 'tier': 'X', 'volume': avg_volume, 'atr': avg_atr, 
                'dsg_count': dsg_count, 'diamond_count': diamond_count}
        
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

def run_tier_categorization():
    print("=" * 80)
    print(f"🏆 TRADING-OPTIMIZED TIER CATEGORIZATION")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    print(f"\nCategorizing {len(DEFAULT_COINS)} coins...\n")
    
    all_tiers = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(DEFAULT_COINS)} coins categorized...")
        
        tier_data = categorize_coin_tier(symbol)
        if tier_data:
            all_tiers.append(tier_data)
    
    if len(all_tiers) < 10:
        print("\n❌ Insufficient data")
        return
    
    df = pd.DataFrame(all_tiers)
    
    # Statistics
    print(f"\n{'═' * 80}")
    print("📊 TIER DISTRIBUTION")
    print(f"{'═' * 80}")
    
    tier_order = ['A', 'B', 'C', 'D', 'X']
    tier_names = {
        'A': 'Çok Yüksek Likidite (>5B)',
        'B': 'Yüksek Likidite (1B-5B)',
        'C': 'Orta Likidite (100M-1B)',
        'D': 'Düşük Likidite (10M-100M)',
        'X': 'Çok Düşük Likidite (<10M)'
    }
    
    for tier in tier_order:
        tier_df = df[df['tier'] == tier]
        if tier_df.empty:
            continue
        
        count = len(tier_df)
        pct = (count / len(df)) * 100
        
        print(f"\n{'─' * 80}")
        print(f"🔹 TIER {tier}: {tier_names[tier]} ({count} koin, {pct:.1f}%)")
        print(f"{'─' * 80}")
        
        # Stats
        print(f"Ortalama Hacim: ${tier_df['volume'].mean():,.0f}")
        print(f"Ortalama ATR%: {tier_df['atr'].mean():.2f}%")
        print(f"Toplam DSG Ralli: {tier_df['dsg_count'].sum():.0f}")
        print(f"Toplam Diamond: {tier_df['diamond_count'].sum():.0f}")
        
        # Sample coins
        sample = tier_df.sort_values('dsg_count', ascending=False)['symbol'].head(10).tolist()
        print(f"Örnek (En Çok Ralli): {', '.join(sample)}")
    
    # Save results
    output_file = coin_cell_paths.get_library_root() / "coin_tiers.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n{'═' * 80}")
    print(f"✅ Tier Categorization Complete")
    print(f"Results saved to: {output_file}")
    print(f"{'═' * 80}")
    
    # Strategy recommendations
    print(f"\n{'═' * 80}")
    print("🎯 AYAŞ TÜNELİ İÇİN ÖNERİLER")
    print(f"{'═' * 80}")
    
    tier_a_count = len(df[df['tier'] == 'A'])
    tier_b_count = len(df[df['tier'] == 'B'])
    tier_c_count = len(df[df['tier'] == 'C'])
    
    print(f"\n✅ ÖNCELİK 1: TIER A ({tier_a_count} koin)")
    print("   → En güvenilir, en likit, optimal volatilite")
    
    if tier_b_count > 0:
        print(f"\n✅ ÖNCELİK 2: TIER B ({tier_b_count} koin)")
        print("   → Yüksek kazanç potansiyeli, kabul edilebilir risk")
    
    if tier_c_count > 0:
        print(f"\n📍 MUHAFAZAKAR: TIER C ({tier_c_count} koin)")
        print("   → Düşük risk, tutarlı küçük kazançlar")
    
    print(f"\n⚠️  TIER D: Portföyün max %20'si")
    print(f"❌ TIER X: İşlem yapma")

if __name__ == "__main__":
    run_tier_categorization()
