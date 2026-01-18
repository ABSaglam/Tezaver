"""
Phase 3: Detailed Trend Entry Conditions Analysis
==================================================
Analyze what specific conditions precede each rally archetype and tier.
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

def get_detailed_pre_conditions(symbol, start_time):
    """Get detailed indicator values before a rally."""
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return None
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        pre_idx = df[df['timestamp'] < start_ts].index
        
        if len(pre_idx) < 20:
            return None
        
        idx = pre_idx[-1]
        
        # Calculate all indicators
        df['rsi'] = calculate_rsi(df['close'], 14)
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        
        # Bollinger Bands
        df['bb_mid'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
        
        close = df.loc[idx, 'close']
        
        return {
            # RSI
            'rsi': df.loc[idx, 'rsi'],
            'rsi_zone': 'oversold' if df.loc[idx, 'rsi'] < 30 else ('overbought' if df.loc[idx, 'rsi'] > 70 else 'neutral'),
            
            # ATR
            'atr_pct': df.loc[idx, 'atr'],
            'atr_vs_avg': df.loc[idx, 'atr'] / df['atr'].rolling(20).mean().loc[idx] if df['atr'].rolling(20).mean().loc[idx] > 0 else 1,
            
            # Trend
            'above_ema9': 1 if close > df.loc[idx, 'ema9'] else 0,
            'above_ema20': 1 if close > df.loc[idx, 'ema20'] else 0,
            'above_ema50': 1 if close > df.loc[idx, 'ema50'] else 0,
            'ema9_above_ema20': 1 if df.loc[idx, 'ema9'] > df.loc[idx, 'ema20'] else 0,
            'ema20_above_ema50': 1 if df.loc[idx, 'ema20'] > df.loc[idx, 'ema50'] else 0,
            
            # Volume
            'vol_ratio': df.loc[idx, 'volume'] / df.loc[idx, 'vol_ma20'] if df.loc[idx, 'vol_ma20'] > 0 else 1,
            
            # Bollinger
            'bb_position': 'lower' if close < df.loc[idx, 'bb_lower'] else ('upper' if close > df.loc[idx, 'bb_upper'] else 'mid'),
            'bb_width': (df.loc[idx, 'bb_upper'] - df.loc[idx, 'bb_lower']) / df.loc[idx, 'bb_mid'] * 100 if df.loc[idx, 'bb_mid'] > 0 else 0
        }
        
    except Exception as e:
        return None

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_trend_entry_analysis():
    print("=" * 80)
    print("🎯 AŞAMA 3: TREND GİRİŞ KOŞULLARI ANALİZİ")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load rallies with archetypes
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT symbol, tier, archetype, raw_data 
        FROM rallies 
        WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER') 
        AND archetype IS NOT NULL
    """
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Toplam ralli: {len(df_rallies)}")
    
    # Sample for analysis
    sample_size = min(15000, len(df_rallies))
    df_sample = df_rallies.sample(n=sample_size, random_state=42)
    
    print(f"Örnek boyutu: {sample_size}")
    
    results = []
    
    for i, row in df_sample.iterrows():
        if (len(results) + 1) % 2000 == 0:
            print(f"İlerleme: {len(results)+1}/{sample_size}")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        if raw_data is None:
            continue
            
        symbol = raw_data.get('symbol', row.get('symbol', ''))
        start_time = raw_data.get('start_time')
        
        if not start_time:
            continue
        
        conditions = get_detailed_pre_conditions(symbol, start_time)
        
        if conditions:
            conditions['symbol'] = symbol
            conditions['tier'] = row['tier']
            conditions['archetype'] = row['archetype']
            results.append(conditions)
    
    df = pd.DataFrame(results)
    
    if df.empty:
        print("❌ Veri yok")
        return
    
    print(f"\n✅ {len(df)} ralli koşulu analiz edildi")
    
    # Analyze by Archetype
    print("\n" + "=" * 80)
    print("📊 ARKETİP BAZINDA GİRİŞ KOŞULLARI")
    print("=" * 80)
    
    for archetype in ['SUPERNOVA', 'MERDIVEN', 'GRIND', 'BREAKOUT']:
        arch_df = df[df['archetype'] == archetype]
        if arch_df.empty or len(arch_df) < 10:
            continue
        
        print(f"\n{'─' * 60}")
        print(f"🔹 {archetype} ({len(arch_df)} ralli)")
        print(f"{'─' * 60}")
        
        print(f"RSI: Ortalama={arch_df['rsi'].mean():.1f}, Medyan={arch_df['rsi'].median():.1f}")
        print(f"RSI Zone: {arch_df['rsi_zone'].value_counts(normalize=True).mul(100).round(1).to_dict()}")
        
        print(f"ATR%: Ortalama={arch_df['atr_pct'].mean():.2f}")
        
        print(f"EMA20 üzerinde: {arch_df['above_ema20'].mean()*100:.1f}%")
        print(f"EMA50 üzerinde: {arch_df['above_ema50'].mean()*100:.1f}%")
        print(f"EMA9>EMA20: {arch_df['ema9_above_ema20'].mean()*100:.1f}%")
        
        print(f"Hacim Oranı: Ortalama={arch_df['vol_ratio'].mean():.2f}x")
        
        print(f"BB Position: {arch_df['bb_position'].value_counts(normalize=True).mul(100).round(1).to_dict()}")
    
    # Analyze by Tier
    print("\n" + "=" * 80)
    print("📊 TİER BAZINDA GİRİŞ KOŞULLARI")
    print("=" * 80)
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        tier_df = df[df['tier'] == tier]
        if tier_df.empty:
            continue
        
        print(f"\n{'─' * 60}")
        print(f"🔹 {tier} ({len(tier_df)} ralli)")
        print(f"{'─' * 60}")
        
        print(f"RSI: Ortalama={tier_df['rsi'].mean():.1f}")
        print(f"RSI Zone: {tier_df['rsi_zone'].value_counts(normalize=True).mul(100).round(1).to_dict()}")
        print(f"EMA20 üzerinde: {tier_df['above_ema20'].mean()*100:.1f}%")
        print(f"Hacim Oranı: Ortalama={tier_df['vol_ratio'].mean():.2f}x")
    
    # Key Patterns
    print("\n" + "=" * 80)
    print("🎯 ANAHTAR ÖRÜNTÜLER")
    print("=" * 80)
    
    # SUPERNOVA Diamond
    supernova_diamond = df[(df['archetype'] == 'SUPERNOVA') & (df['tier'] == 'DIAMOND')]
    if len(supernova_diamond) > 5:
        print(f"\n⭐ SUPERNOVA DIAMOND ({len(supernova_diamond)} ralli):")
        print(f"   RSI: {supernova_diamond['rsi'].mean():.1f}")
        print(f"   EMA20 üzerinde: {supernova_diamond['above_ema20'].mean()*100:.1f}%")
        print(f"   Hacim: {supernova_diamond['vol_ratio'].mean():.2f}x")
    
    # MERDIVEN Diamond
    merdiven_diamond = df[(df['archetype'] == 'MERDIVEN') & (df['tier'] == 'DIAMOND')]
    if len(merdiven_diamond) > 5:
        print(f"\n📶 MERDİVEN DIAMOND ({len(merdiven_diamond)} ralli):")
        print(f"   RSI: {merdiven_diamond['rsi'].mean():.1f}")
        print(f"   EMA20 üzerinde: {merdiven_diamond['above_ema20'].mean()*100:.1f}%")
        print(f"   Hacim: {merdiven_diamond['vol_ratio'].mean():.2f}x")
    
    # Save detailed results
    output_file = coin_cell_paths.get_library_root() / "trend_entry_conditions.csv"
    df.to_csv(output_file, index=False)
    
    print("\n" + "=" * 80)
    print(f"✅ Detaylı veriler: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    run_trend_entry_analysis()
