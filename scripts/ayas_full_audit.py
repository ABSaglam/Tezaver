"""
Ayaş Tüneli Full Database Performance Audit (2024-2026)
======================================================
Bu script, tüm coin hücrelerini tarar, Ayaş Tüneli sinyallerini tespit eder
ve 24 saatlik (96 bar) lookahead ile başarı oranlarını hesaplar.
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths
from tezaver.mining.ayas_tuneli import AYAS_TUNELI_V1
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct

# ⚠️ ÖNEMLİ: Scripts directory'de çalıştırılacağını varsayıyoruz veya absolute path kullanıyoruz
BASE_DIR = Path("/Users/alisaglam/TezaverMac")
COIN_CELL_DIR = BASE_DIR / "coin_cells"
OUTPUT_FILE = BASE_DIR / "analysis" / "ayas_full_audit_2024_2026.csv"

def calculate_atr_pct_all(df_1d):
    """Vectorized ATR% calculation for all rows in 1d DataFrame."""
    df = df_1d.copy()
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_pct = (atr / df['close']) * 100
    return atr_pct

def calculate_rsi_all(df_4h):
    """Vectorized RSI calculation for all rows in 4h DataFrame."""
    df = df_4h.copy()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def audit_symbol(symbol):
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        path_4h = coin_cell_paths.get_history_file(symbol, '4h')
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        
        if not all([path_1d.exists(), path_4h.exists(), path_15m.exists()]):
            return []
            
        df_1d = pd.read_parquet(path_1d).sort_values('timestamp')
        df_4h = pd.read_parquet(path_4h).sort_values('timestamp')
        df_15m = pd.read_parquet(path_15m).sort_values('timestamp')
        
        # 1. Indicators
        df_1d['atr_pct'] = calculate_atr_pct_all(df_1d)
        df_4h['rsi'] = calculate_rsi_all(df_4h)
        
        # 2. Merge Indicators to 15m (Alignment)
        # Using merge_asof for precise point-in-time matching
        # 1d and 4h data must look back (direction='backward')
        df_combined = pd.merge_asof(
            df_15m, 
            df_1d[['timestamp', 'atr_pct']], 
            on='timestamp', 
            direction='backward'
        )
        df_combined = pd.merge_asof(
            df_combined, 
            df_4h[['timestamp', 'rsi']], 
            on='timestamp', 
            direction='backward'
        )
        
        # 3. Ayaş Tüneli Criteria
        t_crit = AYAS_TUNELI_V1['criteria']['TREND']
        n_crit = AYAS_TUNELI_V1['criteria']['NINJA']
        
        df_combined['is_trend'] = (df_combined['atr_pct'] >= t_crit['atr_min']) & \
                                 (df_combined['rsi'] >= t_crit['rsi_min']) & \
                                 (df_combined['rsi'] <= t_crit['rsi_max'])
                                 
        df_combined['is_ninja'] = (df_combined['atr_pct'] >= n_crit['atr_min']) & \
                                 (df_combined['rsi'] >= n_crit['rsi_min']) & \
                                 (df_combined['rsi'] <= n_crit['rsi_max'])
                                 
        df_combined['signal'] = df_combined['is_trend'] | df_combined['is_ninja']
        df_combined['signal_type'] = np.where(df_combined['is_trend'], 'TREND', 
                                             np.where(df_combined['is_ninja'], 'NINJA', None))
        
        # Pick only signal bars
        signals = df_combined[df_combined['signal']].copy()
        
        if signals.empty:
            return []
            
        # 4. Success Calculation (Oracle Mode) with Lockout
        results = []
        last_signal_time = None
        
        for idx, row in signals.iterrows():
            current_time = row['timestamp']
            
            # Lockout: Don't trigger another signal if it's within 24 hours of the last one
            if last_signal_time is not None and (current_time - last_signal_time) < (24 * 3600 * 1000):
                continue
                
            signal_idx = idx
            # Lookahead window: 96 bars (24 hours)
            lookahead_start = signal_idx + 1
            lookahead_end = signal_idx + 97
            
            # Slice lookahead data
            future_df = df_combined.iloc[lookahead_start:lookahead_end]
            
            if future_df.empty:
                continue
                
            entry_price = row['close']
            max_high = future_df['high'].max()
            min_low = future_df['low'].min()
            
            # Pass decimals to compute_tier_from_gain_pct
            peak_gain_decimal = (max_high - entry_price) / entry_price
            max_drawdown_decimal = (min_low - entry_price) / entry_price
            
            tier = compute_tier_from_gain_pct(peak_gain_decimal)
            
            if tier is None: continue # Skip if negative or too low (< 0%)
            
            results.append({
                'symbol': symbol,
                'signal_time': row['datetime'],
                'signal_type': row['signal_type'],
                'atr_pct': round(row['atr_pct'], 2),
                'rsi': round(row['rsi'], 2),
                'peak_gain': round(peak_gain_decimal * 100, 2),
                'max_drawdown': round(max_drawdown_decimal * 100, 2),
                'spread': round(((max_high - min_low) / min_low) * 100, 2),
                'tier': tier
            })
            
            last_signal_time = current_time
            
        return results
        
    except Exception as e:
        print(f"Error auditing {symbol}: {e}")
        return []

def run_audit():
    all_results = []
    total = len(DEFAULT_COINS)
    
    # Create analysis directory if not exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print(f"🚀 AYAŞ TÜNELİ FULL AUDIT START ({datetime.now().strftime('%H:%M')})")
    print(f"Total Symbols: {total}")
    print("=" * 60)
    
    start_time = time.time()
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 20 == 0:
            elapsed = time.time() - start_time
            print(f"[{i}/{total}] {symbol} analiz ediliyor... (Elapsed: {elapsed:.1f}s)")
            
        results = audit_symbol(symbol)
        all_results.extend(results)
        
    if not all_results:
        print("\n❌ Hiçbir sinyal bulunamadı.")
        return
        
    df_results = pd.DataFrame(all_results)
    df_results.to_csv(OUTPUT_FILE, index=False)
    
    # Summary Report
    print("\n" + "=" * 60)
    print("📊 GENEL BAŞARI RAPORU (24 Saatlik Lookahead)")
    print("=" * 60)
    
    total_signals = len(df_results)
    tier_counts = df_results['tier'].value_counts()
    
    print(f"Toplam Sinyal: {total_signals}")
    print("-" * 30)
    for tier in ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON']:
        count = tier_counts.get(tier, 0)
        pct = (count / total_signals) * 100
        print(f"{tier:<10}: {count:>5} ({pct:>5.1f}%)")
    
    print("-" * 30)
    silver_plus = tier_counts.get('DIAMOND', 0) + tier_counts.get('GOLD', 0) + tier_counts.get('SILVER', 0)
    silver_plus_pct = (silver_plus / total_signals) * 100
    print(f"SILVER+ (Ralli Başarısı): %{silver_plus_pct:.1f}")
    print("-" * 60)
    
    # Yearly/Monthly Success
    df_results['year_month'] = pd.to_datetime(df_results['signal_time']).dt.to_period('M')
    monthly_stats = df_results.groupby('year_month').apply(
        lambda x: (x['tier'].isin(['DIAMOND', 'GOLD', 'SILVER']).sum() / len(x)) * 100
    )
    
    print("\n📅 AYLIK BAŞARI ORANLARI (%)")
    print("-" * 30)
    for month, rate in monthly_stats.items():
        print(f"{str(month):<8}: %{rate:>5.1f}")
    
    print("\n✅ Denetim tamamlandı. Detaylı rapor: analysis/ayas_full_audit_2024_2026.csv")
    print("=" * 60)

if __name__ == "__main__":
    run_audit()
