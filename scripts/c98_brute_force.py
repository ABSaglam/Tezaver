"""
C98USDT FULL BRUTE FORCE Sweep
================================
HER ŞEYİ DENİYORUZ:
- Tüm göstergeler
- Momentum, Dip, Hybrid
- Farklı kombinasyonlar
- %100 precision bulana kadar!
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def test_strategy(df_1d, rally_results, rule_func, rule_name):
    """Test a strategy and return precision if >= 5 signals"""
    signals = []
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        if rule_func(row):
            next_date = df_1d.loc[idx+1, 'datetime'].date()
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
    print(f"🔬 {symbol} - FULL BRUTE FORCE")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Tüm göstergeler
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['mom_10d'] = (df_1d['close'] / df_1d['close'].shift(10) - 1) * 100
    df_1d['mom_14d'] = (df_1d['close'] / df_1d['close'].shift(14) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['high_low'] = (df_1d['high'] / df_1d['low'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    # RSI
    delta = df_1d['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df_1d['rsi'] = 100 - (100 / (1 + rs))
    
    best_results = []
    
    print("\n🔍 DIP STRATEJİLERİ (Negatif momentum):")
    print("-" * 70)
    for m7 in [-10, -8, -5, -3, -2, -1]:
        for m3 in [-5, -3, -2, -1]:
            result = test_strategy(df_1d, rally_results,
                lambda r, m7=m7, m3=m3: r['mom_7d'] <= m7 and r['mom_3d'] <= m3,
                f"mom_7d<={m7} & mom_3d<={m3}")
            if result:
                total, hits, prec = result
                if prec >= 90:
                    best_results.append((prec, total, f"DIP: mom_7d<={m7} & mom_3d<={m3}"))
                    marker = " ✅" if prec == 100 else ""
                    print(f"  mom_7d<={m7} & mom_3d<={m3}: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n🔍 RSI STRATEJİLERİ:")
    print("-" * 70)
    for rsi_low in [20, 25, 30, 35]:
        for rsi_high in [65, 70, 75, 80]:
            # RSI oversold
            result = test_strategy(df_1d, rally_results,
                lambda r, rsi_low=rsi_low: r['rsi'] <= rsi_low,
                f"rsi<={rsi_low}")
            if result:
                total, hits, prec = result
                if prec >= 90:
                    best_results.append((prec, total, f"RSI OVERSOLD: rsi<={rsi_low}"))
                    marker = " ✅" if prec == 100 else ""
                    print(f"  rsi<={rsi_low}: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
            
            # RSI overbought
            result = test_strategy(df_1d, rally_results,
                lambda r, rsi_high=rsi_high: r['rsi'] >= rsi_high,
                f"rsi>={rsi_high}")
            if result:
                total, hits, prec = result
                if prec >= 90:
                    best_results.append((prec, total, f"RSI OVERBOUGHT: rsi>={rsi_high}"))
                    marker = " ✅" if prec == 100 else ""
                    print(f"  rsi>={rsi_high}: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n🔍 VOLUME STRATEJİLERİ:")
    print("-" * 70)
    for vol in [1.5, 2.0, 2.5, 3.0]:
        for m7 in [3, 5, 8]:
            result = test_strategy(df_1d, rally_results,
                lambda r, vol=vol, m7=m7: r['vol_ratio'] >= vol and r['mom_7d'] >= m7,
                f"vol_ratio>={vol} & mom_7d>={m7}")
            if result:
                total, hits, prec = result
                if prec >= 90:
                    best_results.append((prec, total, f"VOLUME: vol>={vol} & mom_7d>={m7}"))
                    marker = " ✅" if prec == 100 else ""
                    print(f"  vol>={vol} & mom_7d>={m7}: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n🔍 ULTRA COMPLEX (4-way combos):")
    print("-" * 70)
    for m7 in [5, 8, 10, 12, 15]:
        for ema in [3, 5, 8]:
            for rsi_min in [40, 45, 50]:
                for vol_min in [1.0, 1.5, 2.0]:
                    result = test_strategy(df_1d, rally_results,
                        lambda r, m7=m7, ema=ema, rsi_min=rsi_min, vol_min=vol_min: 
                        r['mom_7d'] >= m7 and r['ema_dist'] >= ema and r['rsi'] >= rsi_min and r['vol_ratio'] >= vol_min,
                        f"COMPLEX")
                    if result:
                        total, hits, prec = result
                        if prec >= 95:
                            best_results.append((prec, total, f"COMPLEX: m7>={m7}, ema>={ema}, rsi>={rsi_min}, vol>={vol_min}"))
                            marker = " ✅" if prec == 100 else ""
                            print(f"  m7>={m7} & ema>={ema} & rsi>={rsi_min} & vol>={vol_min}: {total} sinyal → {prec:.1f}%{marker}")
    
    # Sonuçları sırala
    best_results.sort(reverse=True)
    
    print("\n" + "="*70)
    print("TOP 10 EN İYİ SONUÇLAR:")
    print("="*70)
    for i, (prec, total, rule) in enumerate(best_results[:10], 1):
        marker = " 🎯" if prec == 100 else ""
        print(f"{i}. {prec:.1f}% ({total} sinyal) - {rule}{marker}")

if __name__ == "__main__":
    main()
