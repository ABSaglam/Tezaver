"""
Enhanced Coin Entry Classification
===================================
1. Add RSI-EMA indicator
2. Find natural breakpoints (histogram)
3. Detect most determining factor per coin
4. Correlation analysis for Diamond prediction
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3
from scipy import stats

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_rsi_ema(prices, rsi_period=14, ema_period=9):
    """RSI smoothed with EMA."""
    rsi = calculate_rsi(prices, rsi_period)
    rsi_ema = rsi.ewm(span=ema_period).mean()
    return rsi, rsi_ema

def get_enhanced_conditions(symbol, start_time):
    """Get enhanced indicator values including RSI-EMA."""
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return None
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        pre_idx = df[df['timestamp'] < start_ts].index
        
        if len(pre_idx) < 30:
            return None
        
        idx = pre_idx[-1]
        
        # RSI and RSI-EMA
        df['rsi'], df['rsi_ema'] = calculate_rsi_ema(df['close'])
        
        # Other indicators
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        close = df.loc[idx, 'close']
        rsi = df.loc[idx, 'rsi']
        rsi_ema = df.loc[idx, 'rsi_ema']
        
        return {
            'rsi': rsi,
            'rsi_ema': rsi_ema,
            'rsi_above_rsi_ema': 1 if rsi > rsi_ema else 0,  # RSI cross above
            'rsi_ema_momentum': rsi - rsi_ema,  # Momentum signal
            'above_ema20': 1 if close > df.loc[idx, 'ema20'] else 0,
            'vol_ratio': df.loc[idx, 'volume'] / df.loc[idx, 'vol_ma20'] if df.loc[idx, 'vol_ma20'] > 0 else 1,
            'atr': df.loc[idx, 'atr']
        }
        
    except Exception as e:
        return None

def run_enhanced_analysis():
    print("=" * 80)
    print("🎯 GELİŞMİŞ GİRİŞ KOŞULLARI ANALİZİ")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load rallies
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT symbol, tier, raw_data FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    # Sample
    sample_size = min(20000, len(df_rallies))
    df_sample = df_rallies.sample(n=sample_size, random_state=42)
    
    print(f"Örneklem: {sample_size} ralli")
    
    results = []
    
    for i, row in df_sample.iterrows():
        if (len(results) + 1) % 3000 == 0:
            print(f"İlerleme: {len(results)+1}/{sample_size}")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        if raw_data is None:
            continue
            
        symbol = raw_data.get('symbol', '')
        start_time = raw_data.get('start_time')
        
        if not start_time:
            continue
        
        conditions = get_enhanced_conditions(symbol, start_time)
        
        if conditions:
            conditions['symbol'] = symbol
            conditions['tier'] = row['tier']
            conditions['is_diamond'] = 1 if row['tier'] == 'DIAMOND' else 0
            results.append(conditions)
    
    df = pd.DataFrame(results)
    
    print(f"\n✅ {len(df)} ralli analiz edildi")
    
    # === ANALYSIS 1: Natural Breakpoints ===
    print("\n" + "=" * 80)
    print("📊 ANALİZ 1: DOĞAL KIRILIM NOKTALARI")
    print("=" * 80)
    
    for col in ['rsi', 'rsi_ema', 'rsi_ema_momentum', 'vol_ratio', 'atr']:
        data = df[col].dropna()
        q25, q50, q75 = data.quantile([0.25, 0.5, 0.75])
        print(f"\n{col.upper()}:")
        print(f"   %25: {q25:.2f}")
        print(f"   %50 (Medyan): {q50:.2f}")
        print(f"   %75: {q75:.2f}")
    
    # === ANALYSIS 2: Correlation with Diamond ===
    print("\n" + "=" * 80)
    print("📊 ANALİZ 2: DIAMOND TAHMİN KORELASYONU")
    print("=" * 80)
    
    features = ['rsi', 'rsi_ema', 'rsi_above_rsi_ema', 'rsi_ema_momentum', 'above_ema20', 'vol_ratio', 'atr']
    
    correlations = {}
    for feat in features:
        corr, pval = stats.pointbiserialr(df[feat].fillna(0), df['is_diamond'])
        correlations[feat] = corr
        significance = "***" if pval < 0.001 else ("**" if pval < 0.01 else ("*" if pval < 0.05 else ""))
        print(f"{feat:20s}: r={corr:+.4f} {significance}")
    
    best_predictor = max(correlations, key=lambda x: abs(correlations[x]))
    print(f"\n🏆 En İyi Diamond Tahmin Edicisi: {best_predictor} (r={correlations[best_predictor]:.4f})")
    
    # === ANALYSIS 3: Most Determining Factor per Coin ===
    print("\n" + "=" * 80)
    print("📊 ANALİZ 3: COİN BAZINDA EN BELİRLEYİCİ FAKTÖR")
    print("=" * 80)
    
    coin_factors = []
    
    for symbol in df['symbol'].unique():
        coin_df = df[df['symbol'] == symbol]
        if len(coin_df) < 10:
            continue
        
        # Find which factor varies most for this coin's rallies
        coin_corrs = {}
        for feat in features:
            if feat in coin_df.columns:
                std = coin_df[feat].std()
                coin_corrs[feat] = std
        
        if coin_corrs:
            most_variable = max(coin_corrs, key=coin_corrs.get)
            coin_factors.append({
                'symbol': symbol,
                'most_variable_factor': most_variable,
                'rallies': len(coin_df)
            })
    
    factor_df = pd.DataFrame(coin_factors)
    
    print("\nEn Belirleyici Faktör Dağılımı:")
    factor_counts = factor_df['most_variable_factor'].value_counts()
    for fact, count in factor_counts.items():
        print(f"   {fact:20s}: {count:3d} coin")
    
    # === RSI-EMA Specific Insights ===
    print("\n" + "=" * 80)
    print("📊 RSI-EMA ÖZEL ANALİZ")
    print("=" * 80)
    
    # RSI above RSI-EMA = bullish momentum
    rsi_cross_up = df[df['rsi_above_rsi_ema'] == 1]
    rsi_cross_down = df[df['rsi_above_rsi_ema'] == 0]
    
    print(f"\nRSI > RSI-EMA (Yükseliş Momentumu):")
    print(f"   Ralli sayısı: {len(rsi_cross_up)}")
    print(f"   Diamond oranı: {rsi_cross_up['is_diamond'].mean()*100:.1f}%")
    
    print(f"\nRSI < RSI-EMA (Düşüş Momentumu):")
    print(f"   Ralli sayısı: {len(rsi_cross_down)}")
    print(f"   Diamond oranı: {rsi_cross_down['is_diamond'].mean()*100:.1f}%")
    
    # Save
    output_file = coin_cell_paths.get_library_root() / "enhanced_entry_analysis.csv"
    df.to_csv(output_file, index=False)
    
    print("\n" + "=" * 80)
    print(f"✅ Detaylı veriler: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    run_enhanced_analysis()
