"""
Comprehensive Coin Exploratory Analysis
========================================
Pure observation - no categorization. Just report what we see.
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

def analyze_coin_comprehensive(symbol):
    """Comprehensive analysis of a single coin."""
    try:
        # Load data
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return None
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        if len(df) < 100:
            return None
        
        # === DSG PERFORMANCE ===
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT tier, COUNT(*) as count FROM rallies WHERE symbol = '{symbol}' AND tier IN ('DIAMOND', 'GOLD', 'SILVER') GROUP BY tier"
        dsg_counts = pd.read_sql_query(query, conn)
        conn.close()
        
        diamond_count = dsg_counts[dsg_counts['tier'] == 'DIAMOND']['count'].sum() if 'DIAMOND' in dsg_counts['tier'].values else 0
        gold_count = dsg_counts[dsg_counts['tier'] == 'GOLD']['count'].sum() if 'GOLD' in dsg_counts['tier'].values else 0
        silver_count = dsg_counts[dsg_counts['tier'] == 'SILVER']['count'].sum() if 'SILVER' in dsg_counts['tier'].values else 0
        
        # === TREND BEHAVIOR ===
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        
        # Trend direction
        df['in_uptrend'] = (df['close'] > df['ema20']).astype(int)
        
        # Trend changes (how often it changes direction)
        df['trend_change'] = (df['in_uptrend'] != df['in_uptrend'].shift()).astype(int)
        trend_change_count = df['trend_change'].sum()
        
        # Average trend duration
        trend_groups = (df['in_uptrend'] != df['in_uptrend'].shift()).cumsum()
        trend_durations = df.groupby(trend_groups).size()
        avg_trend_duration_days = trend_durations.mean()
        
        # Trend loyalty (% of time respecting EMA20)
        # When price crosses above EMA, does it stay above for a while?
        uptrend_periods = df[df['in_uptrend'] == 1]
        if len(uptrend_periods) > 0:
            uptrend_continuity = len(uptrend_periods) / len(df) * 100
        else:
            uptrend_continuity = 0
        
        # === FAKEOUT MEASUREMENT ===
        # When price breaks above EMA20, does it immediately fall back?
        df['ema_cross_up'] = ((df['in_uptrend'] == 1) & (df['in_uptrend'].shift(1) == 0)).astype(int)
        df['quick_reversal'] = ((df['ema_cross_up'] == 1) & (df['in_uptrend'].shift(-1) == 0)).astype(int)
        
        fakeout_count = df['quick_reversal'].sum()
        crossup_count = df['ema_cross_up'].sum()
        fakeout_rate = (fakeout_count / crossup_count * 100) if crossup_count > 0 else 0
        
        # === VOLATILITY ===
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        avg_atr = df['atr'].mean()
        
        # === WICK ANALYSIS ===
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['wick_total'] = df['range'] - df['body']
        df['wick_ratio'] = (df['wick_total'] / df['range'] * 100).fillna(0)
        avg_wick_ratio = df['wick_ratio'].mean()
        
        # === VOLUME ===
        avg_volume = df['volume'].mean()
        
        return {
            'symbol': symbol,
            # DSG Performance
            'diamond_count': int(diamond_count),
            'gold_count': int(gold_count),
            'silver_count': int(silver_count),
            'total_dsg': int(diamond_count + gold_count + silver_count),
            # Trend Behavior
            'avg_trend_duration_days': round(avg_trend_duration_days, 1),
            'trend_changes': int(trend_change_count),
            'uptrend_continuity_pct': round(uptrend_continuity, 1),
            # Loyalty/Fakeout
            'fakeout_rate_pct': round(fakeout_rate, 1),
            'fakeout_count': int(fakeout_count),
            # Volatility & Wicks
            'avg_atr_pct': round(avg_atr, 2),
            'avg_wick_ratio_pct': round(avg_wick_ratio, 1),
            # Volume
            'avg_volume': int(avg_volume)
        }
        
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

def generate_exploratory_report():
    print("=" * 80)
    print("📊 COMPREHENSIVE COIN EXPLORATORY ANALYSIS")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    results = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(DEFAULT_COINS)} coins analyzed...")
        
        coin_data = analyze_coin_comprehensive(symbol)
        if coin_data:
            results.append(coin_data)
    
    df = pd.DataFrame(results)
    
    if df.empty:
        print("\n❌ No data")
        return
    
    # Save raw data
    output_file = coin_cell_paths.get_library_root() / "coin_exploration.csv"
    df.to_csv(output_file, index=False)
    
    # === GENERATE REPORT ===
    print("\n" + "=" * 80)
    print("📈 GÖZLEMLER VE DAĞILIMLAR")
    print("=" * 80)
    
    # DSG Performance Distribution
    print("\n🎯 DSG PERFORMANSI:")
    print(f"   Hiç Diamond yapmayan: {len(df[df['diamond_count'] == 0])} koin")
    print(f"   1-5 Diamond: {len(df[(df['diamond_count'] > 0) & (df['diamond_count'] <= 5)])} koin")
    print(f"   6-10 Diamond: {len(df[(df['diamond_count'] > 5) & (df['diamond_count'] <= 10)])} koin")
    print(f"   10+ Diamond: {len(df[df['diamond_count'] > 10])} koin")
    print(f"\n   En çok Diamond yapan Top 10:")
    top_diamonds = df.nlargest(10, 'diamond_count')[['symbol', 'diamond_count', 'gold_count', 'silver_count']]
    for _, row in top_diamonds.iterrows():
        print(f"      {row['symbol']:15s}: D={row['diamond_count']:2.0f}, G={row['gold_count']:2.0f}, S={row['silver_count']:3.0f}")
    
    # Trend Loyalty
    print("\n🎭 SAMİMİYET (Trend Sadakati):")
    print(f"   Ortalama trend süresi: {df['avg_trend_duration_days'].mean():.1f} gün")
    print(f"   Medyan: {df['avg_trend_duration_days'].median():.1f} gün")
    print(f"   En sadık (uzun trendler) Top 10:")
    loyal = df.nlargest(10, 'avg_trend_duration_days')[['symbol', 'avg_trend_duration_days', 'fakeout_rate_pct']]
    for _, row in loyal.iterrows():
        print(f"      {row['symbol']:15s}: {row['avg_trend_duration_days']:5.1f} gün/trend, Fakeout: {row['fakeout_rate_pct']:4.1f}%")
    
    # Fakeout Analysis
    print("\n⚠️  FAKEOUT (Yalancılık) ORANI:")
    print(f"   Ortalama fakeout rate: {df['fakeout_rate_pct'].mean():.1f}%")
    print(f"   En yüksek fakeout (tuzakçılar) Top 10:")
    trappy = df.nlargest(10, 'fakeout_rate_pct')[['symbol', 'fakeout_rate_pct', 'fakeout_count']]
    for _, row in trappy.iterrows():
        print(f"      {row['symbol']:15s}: {row['fakeout_rate_pct']:5.1f}% ({row['fakeout_count']:.0f} fakeout)")
    
    # Volatility
    print("\n📊 VOLATİLİTE:")
    print(f"   Ortalama ATR: {df['avg_atr_pct'].mean():.2f}%")
    print(f"   En volatil Top 10:")
    volatile = df.nlargest(10, 'avg_atr_pct')[['symbol', 'avg_atr_pct']]
    for _, row in volatile.iterrows():
        print(f"      {row['symbol']:15s}: {row['avg_atr_pct']:5.2f}%")
    
    # Wick Ratio
    print("\n🕯️  WICK ORANI (İğne Oranı):")
    print(f"   Ortalama wick ratio: {df['avg_wick_ratio_pct'].mean():.1f}%")
    print(f"   En yüksek wick (en çok iğne atan) Top 10:")
    wicky = df.nlargest(10, 'avg_wick_ratio_pct')[['symbol', 'avg_wick_ratio_pct']]
    for _, row in wicky.iterrows():
        print(f"      {row['symbol']:15s}: {row['avg_wick_ratio_pct']:5.1f}%")
    
    print("\n" + "=" * 80)
    print(f"✅ Analiz tamamlandı. Ham veri: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    generate_exploratory_report()
