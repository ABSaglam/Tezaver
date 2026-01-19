"""
ACMUSDT - Gizem Keşfi
======================
ACM'nin benzersiz ruhunu keşfet.
Hiçbir varsayımda bulunma - sadece verinin söylediklerini dinle.

Train: 2023-2025 | Test: 2026 held out
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACMUSDT'
    print(f"🔍 {symbol} - Gizem Avcılığı Başlıyor...")
    print(f"⚠️  Train: 2023-2025 | Test: 2026 (held out)")
    
    from datetime import timedelta
    rally_signal_dates = set()
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    
    for rally_date in rally_results.keys():
        signal_date = rally_date - timedelta(days=1)
        rally_signal_dates.add(signal_date)
    
    print(f"✓ {len(rally_results)} DG rallies bulundu (train)")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    print(f"✓ {len(df_1d)} candles yüklendi")
    
    print("🔄 İndikatörler hesaplanıyor...")
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['rsi'] = df_1d['close'].diff().apply(lambda x: max(x, 0)).rolling(14).mean() / df_1d['close'].diff().abs().rolling(14).mean() * 100
    
    # Ekstra: Volatilite
    df_1d['volatility'] = df_1d['close'].rolling(10).std() / df_1d['close'].rolling(10).mean() * 100
    print("✓ Hazır")
    
    rally_features = []
    non_rally_features = []
    
    print("🔄 Rally vs Normal günler analizi...")
    for idx in range(25, len(df_1d)):
        row = df_1d.loc[idx]
        sig_date = row['datetime'].date()
        
        entry = {
            'ema_dist': row['ema_dist'],
            'daily_ch': row['daily_ch'],
            'vol_ratio': row['vol_ratio'],
            'mom_5d': row['mom_5d'],
            'mom_3d': row['mom_3d'],
            'mom_7d': row['mom_7d'],
            'rsi': row['rsi'],
            'volatility': row['volatility']
        }
        
        if sig_date in rally_signal_dates:
            rally_features.append(entry)
        else:
            non_rally_features.append(entry)
    
    rally_df = pd.DataFrame(rally_features)
    non_rally_df = pd.DataFrame(non_rally_features)
    
    print("\n" + "="*70)
    print(f"🎯 {symbol} - GİZEM KEŞFİ (TRAIN: 2023-2025)")
    print(f"Rally Günleri: {len(rally_df)} | Normal Günler: {len(non_rally_df)}")
    print("="*70)
    
    print("\n🔥 RALLY GÜNLERİ İstatistikleri:")
    print(rally_df.describe().loc[['mean', '50%', 'min', 'max']])
    
    print("\n❄️ NORMAL GÜNLER İstatistikleri:")
    print(non_rally_df.describe().loc[['mean', '50%', 'min', 'max']])
    
    print("\n" + "="*70)
    print("⚡ AYIRICI GÜÇ ANALİZİ - ACM'nin Ruhu Nerede?")
    print("="*70)
    
    discriminators = []
    for col in ['ema_dist', 'daily_ch', 'vol_ratio', 'mom_5d', 'mom_3d', 'mom_7d', 'rsi', 'volatility']:
        r_mean = rally_df[col].mean()
        nr_mean = non_rally_df[col].mean()
        diff = abs(r_mean - nr_mean)
        diff_pct = ((r_mean - nr_mean) / abs(nr_mean) * 100) if nr_mean != 0 else 0
        
        discriminators.append({
            'indicator': col,
            'rally_mean': r_mean,
            'normal_mean': nr_mean,
            'diff_pct': diff_pct,
            'diff_abs': diff
        })
    
    # Güce göre sırala
    discriminators.sort(key=lambda x: abs(x['diff_pct']), reverse=True)
    
    print(f"\n{'Sıra':<5} {'İndikatör':<12} {'Rally':<10} {'Normal':<10} {'Fark %':<12} {'Güç':<10}")
    print("-" * 70)
    for i, d in enumerate(discriminators, 1):
        power = "🔥🔥🔥" if abs(d['diff_pct']) > 1000 else "🔥🔥" if abs(d['diff_pct']) > 100 else "🔥" if abs(d['diff_pct']) > 10 else "💨"
        print(f"{i:<5} {d['indicator']:<12} {d['rally_mean']:>9.2f} {d['normal_mean']:>9.2f} {d['diff_pct']:>+11.0f}% {power}")
    
    # En güçlü 3'ü detaylı incele
    print("\n" + "="*70)
    print("🔬 EN GÜÇLÜ 3 AYIRICI - Detaylı Bakış")
    print("="*70)
    
    for i, d in enumerate(discriminators[:3], 1):
        ind = d['indicator']
        print(f"\n#{i} - {ind.upper()}")
        print(f"  Rally günleri: Ort={d['rally_mean']:.2f}, Median={rally_df[ind].median():.2f}")
        print(f"  Normal günler: Ort={d['normal_mean']:.2f}, Median={non_rally_df[ind].median():.2f}")
        print(f"  Fark: {d['diff_pct']:+.0f}%")
        
        # Dağılıma bak - pozitif mi negatif mi?
        rally_positive = (rally_df[ind] > 0).sum()
        rally_negative = (rally_df[ind] < 0).sum()
        print(f"  Rally günleri dağılım: {rally_positive} pozitif, {rally_negative} negatif")
        
        if d['rally_mean'] < 0:
            print(f"  ⚠️ DİKKAT: Rally günleri NEGATİF ortalama! (Ters trend sinyali?)")
    
    print("\n✅ Pattern keşfi tamamlandı!")
    print("📌 2026 verisi test için saklı")

if __name__ == "__main__":
    main()

