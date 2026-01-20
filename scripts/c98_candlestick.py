"""
C98USDT - CANDLESTICK PATTERN Analysis
=======================================
Mum formasyonları test ediyoruz:
- Doji (belirsizlik)
- Hammer (dip formasyonu)
- Shooting Star (tepe formasyonu)
- Bullish/Bearish Engulfing
- Morning/Evening Star
- Harami
- Spinning Top
vb.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def detect_patterns(df):
    """Mum formasyonlarını tespit et"""
    
    # Body ve shadow hesapla
    df['body'] = abs(df['close'] - df['open'])
    df['upper_shadow'] = df['high'] - df[['close', 'open']].max(axis=1)
    df['lower_shadow'] = df[['close', 'open']].min(axis=1) - df['low']
    df['total_range'] = df['high'] - df['low']
    df['body_pct'] = df['body'] / df['total_range'] * 100
    
    # Bullish/Bearish
    df['is_bullish'] = df['close'] > df['open']
    
    # DOJI: Çok küçük body (<%5 total range)
    df['doji'] = df['body_pct'] < 5
    
    # HAMMER: Uzun alt shadow, kısa üst shadow, küçük body (dip sinyali)
    df['hammer'] = (
        (df['lower_shadow'] > df['body'] * 2) &
        (df['upper_shadow'] < df['body'] * 0.3) &
        (df['body_pct'] < 30)
    )
    
    # SHOOTING STAR: Uzun üst shadow, kısa alt shadow (tepe sinyali)
    df['shooting_star'] = (
        (df['upper_shadow'] > df['body'] * 2) &
        (df['lower_shadow'] < df['body'] * 0.3) &
        (df['body_pct'] < 30)
    )
    
    # BULLISH ENGULFING: Yeşil mum önceki kırmızıyı yutar
    df['bullish_engulfing'] = (
        df['is_bullish'] &
        (df['is_bullish'].shift(1) == False) &
        (df['open'] < df['close'].shift(1)) &
        (df['close'] > df['open'].shift(1))
    )
    
    # BEARISH ENGULFING
    df['bearish_engulfing'] = (
        (df['is_bullish'] == False) &
        (df['is_bullish'].shift(1) == True) &
        (df['open'] > df['close'].shift(1)) &
        (df['close'] < df['open'].shift(1))
    )
    
    # MARUBOZU: Neredeyse hiç shadow yok (güçlü momentum)
    df['bullish_marubozu'] = (
        df['is_bullish'] &
        (df['body_pct'] > 85)
    )
    
    df['bearish_marubozu'] = (
        (~df['is_bullish']) &
        (df['body_pct'] > 85)
    )
    
    # SPINNING TOP: Küçük body, uzun shadowlar (belirsizlik)
    df['spinning_top'] = (
        (df['body_pct'] < 25) &
        (df['upper_shadow'] > df['body']) &
        (df['lower_shadow'] > df['body'])
    )
    
    return df

def test_pattern(df, rally_results, pattern_col, pattern_name):
    """Pattern test et"""
    signals = []
    for idx in range(25, len(df)-1):
        if df.loc[idx, pattern_col]:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_rally = next_date in rally_results
            signals.append(is_rally)
    
    if len(signals) >= 5:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100
        return total, hits, prec
    return None

def main():
    symbol = 'C98USDT'
    print(f"🔬 {symbol} - CANDLESTICK PATTERN Analysis")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Momentum ekle (pattern + momentum kombinasyonu için)
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    
    # Pattern tespit
    df = detect_patterns(df)
    
    print("\n📊 MUM FORMASYONU TESTLERİ:")
    print("-" * 70)
    
    patterns = [
        ('doji', 'Doji'),
        ('hammer', 'Hammer (Dip Sinyali)'),
        ('shooting_star', 'Shooting Star (Tepe Sinyali)'),
        ('bullish_engulfing', 'Bullish Engulfing'),
        ('bearish_engulfing', 'Bearish Engulfing'),
        ('bullish_marubozu', 'Bullish Marubozu'),
        ('bearish_marubozu', 'Bearish Marubozu'),
        ('spinning_top', 'Spinning Top'),
    ]
    
    best_results = []
    
    for col, name in patterns:
        result = test_pattern(df, rally_results, col, name)
        if result:
            total, hits, prec = result
            marker = " ✅" if prec == 100 else ""
            print(f"  {name:25s}: {total:3d} sinyal, {hits:3d} rally → {prec:5.1f}%{marker}")
            best_results.append((prec, total, name))
    
    print("\n📊 PATTERN + MOMENTUM KOMBİNASYONLARI:")
    print("-" * 70)
    
    # Pattern + momentum kombinasyonları
    for col, name in patterns:
        for m7_thresh in [3, 5, 8]:
            signals = []
            for idx in range(25, len(df)-1):
                if df.loc[idx, col] and df.loc[idx, 'mom_7d'] >= m7_thresh:
                    next_date = df.loc[idx+1, 'datetime'].date()
                    is_rally = next_date in rally_results
                    signals.append(is_rally)
            
            if len(signals) >= 5:
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                marker = " ✅" if prec == 100 else ""
                if prec >= 80:
                    print(f"  {name} + mom_7d>={m7_thresh}: {total} sinyal → {prec:.1f}%{marker}")
                    best_results.append((prec, total, f"{name} + mom_7d>={m7_thresh}"))
    
    # Tersine pattern + dip kombinasyonları
    print("\n📊 PATTERN + DIP KOMBİNASYONLARI:")
    print("-" * 70)
    
    for col, name in [('hammer', 'Hammer'), ('doji', 'Doji')]:
        for m7_thresh in [-5, -3, -2]:
            signals = []
            for idx in range(25, len(df)-1):
                if df.loc[idx, col] and df.loc[idx, 'mom_7d'] <= m7_thresh:
                    next_date = df.loc[idx+1, 'datetime'].date()
                    is_rally = next_date in rally_results
                    signals.append(is_rally)
            
            if len(signals) >= 5:
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                marker = " ✅" if prec == 100 else ""
                if prec >= 80:
                    print(f"  {name} + mom_7d<={m7_thresh}: {total} sinyal → {prec:.1f}%{marker}")
                    best_results.append((prec, total, f"{name} + mom_7d<={m7_thresh}"))
    
    # En iyileri göster
    best_results.sort(reverse=True)
    print("\n" + "="*70)
    print("TOP 10 EN İYİ:")
    print("="*70)
    for i, (prec, total, rule) in enumerate(best_results[:10], 1):
        marker = " 🎯" if prec == 100 else ""
        print(f"{i}. {prec:.1f}% ({total} sinyal) - {rule}{marker}")

if __name__ == "__main__":
    main()
