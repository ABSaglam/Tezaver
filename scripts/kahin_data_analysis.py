import pandas as pd
import numpy as np

FILE = "/Users/alisaglam/TezaverMac/kahin_discovery_results.csv"

def analyze():
    df = pd.read_csv(FILE)
    total_samples = len(df)
    baseline_wr = df['target'].mean() * 100
    
    print(f"🏛️ KAHİN ANALİZ SONUÇLARI (2023-2025)")
    print(f"Toplam Vise Alan Gün Sayısı: {total_samples}")
    print(f"Baz Başarı Oranı (Tier %): {baseline_wr:.2f}%")
    print("-" * 30)

    # 1. BTC Context
    btc_ok_wr = df[df['btc_ok'] == 1]['target'].mean() * 100
    btc_no_wr = df[df['btc_ok'] == 0]['target'].mean() * 100
    print(f"BTC Onaylıyken Başarı: {btc_ok_wr:.2f}%")
    print(f"BTC Onaysızken Başarı: {btc_no_wr:.2f}%")
    
    # 2. RSI Position Analysis
    df['rsi_cat'] = pd.cut(df['rsi_d'], bins=[0, 40, 50, 60, 70, 80, 100])
    rsi_stats = df.groupby('rsi_cat')['target'].agg(['mean', 'count'])
    print("\n🏛️ RSI (GÜNLÜK) SEVİYE ANALİZİ:")
    print(rsi_stats)
    
    # 3. RSI Difference (Distance to Ribbon)
    df['diff_cat'] = pd.cut(df['rsi_diff'], bins=[-100, 0, 5, 10, 20, 100])
    diff_stats = df.groupby('diff_cat')['target'].agg(['mean', 'count'])
    print("\n🏛️ RSI-RIBBON MESAFE ANALİZİ:")
    print(diff_stats)
    
    # 4. Vol MOM Analysis
    df['vol_cat'] = pd.cut(df['vol_mom'], bins=[0, 0.5, 1.0, 1.5, 2.0, 10])
    vol_stats = df.groupby('vol_cat')['target'].agg(['mean', 'count'])
    print("\n🏛️ HACİM MOMENTUM (DÜN) ANALİZİ:")
    print(vol_stats)
    
    # 5. ATR% Analysis
    df['atr_cat'] = pd.cut(df['atr_p'], bins=[0, 2, 4, 6, 8, 20])
    atr_stats = df.groupby('atr_cat')['target'].agg(['mean', 'count'])
    print("\n🏛️ VOLATİLİTE (ATR%) ANALİZİ:")
    print(atr_stats)

    # 🏛️ GENIUS SEÇİMİ: Optimizasyon
    # En yüksek WR veren cluster'ı bulalım.
    best_filter = df[(df['btc_ok'] == 1) & (df['rsi_d'] > 60) & (df['vol_mom'] > 1.0)]
    best_wr = best_filter['target'].mean() * 100
    print(f"\n🏛️ DAHİ FİLTRE ÖNERİSİ:")
    print(f"Kural: BTC OK + RSI(D) > 60 + VolMom > 1.0")
    print(f"Örnek Sayısı: {len(best_filter)}")
    print(f"Filtrelenmiş Başarı Oranı: {best_wr:.2f}%")
    print(f"İyileşme: {best_wr - baseline_wr:.2f}%")

if __name__ == "__main__":
    analyze()
