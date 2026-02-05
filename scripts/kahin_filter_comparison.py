import pandas as pd
import numpy as np

FILE = "/Users/alisaglam/TezaverMac/kahin_discovery_results.csv"

def compare_filters():
    df = pd.read_csv(FILE)
    total_samples = len(df)
    total_d = len(df[df['peak'] >= 30.0])
    
    print(f"🏛️ KAHİN: FİLTRE KIYAS (TOPLAM ELMAS: {total_d})")
    print("-" * 60)
    print(f"{'Filtre':<40} | {'Kalan Gün':<10} | {'Yakalanan D%':<15} | {'Yoğunluk D%'}")
    print("-" * 60)
    
    # 🏛️ FİLTRE 1: HARD (RSI > 60, VolMom > 1.0, BTC OK)
    f1 = (df['btc_ok'] == 1) & (df['rsi_d'] > 60) & (df['vol_mom'] > 1.0)
    d1 = len(df[f1 & (df['peak'] >= 30.0)])
    print(f"{'HARD (RSI>60, Vol>1, BTC)':<40} | {len(df[f1]):<10} | %{(d1/total_d)*100:<13.1f} | %{(d1/len(df[f1]))*100:.2f}")

    # 🏛️ FİLTRE 2: MEDIUM (RSI > 50, VolMom > 0.8)
    f2 = (df['rsi_d'] > 50) & (df['vol_mom'] > 0.8)
    d2 = len(df[f2 & (df['peak'] >= 30.0)])
    print(f"{'MEDIUM (RSI>50, Vol>0.8)':<40} | {len(df[f2]):<10} | %{(d2/total_d)*100:<13.1f} | %{(d2/len(df[f2]))*100:.2f}")

    # 🏛️ FİLTRE 3: SOFT (Sadece Günlük Vize - Mevcut Durum)
    # Zaten CSV'deki tüm satırlar W/D vizesi almış olanlar.
    print(f"{'SOFT (Sadece W/D Vizesi - Baseline)':<40} | {total_samples:<10} | %100.0         | %{(total_d/total_samples)*100:.2f}")

    # 🏛️ FİLTRE 4: VOLATİLİTE ODAKLI (ATR > 6)
    f4 = (df['atr_p'] > 6.0)
    d4 = len(df[f4 & (df['peak'] >= 30.0)])
    print(f"{'VOLATYLE (ATR > 6.0)':<40} | {len(df[f4]):<10} | %{(d4/total_d)*100:<13.1f} | %{(d4/len(df[f4]))*100:.2f}")

    # 🏛️ FİLTRE 5: VOLATİLİTE + HACİM
    f5 = (df['atr_p'] > 6.0) & (df['vol_mom'] > 0.7)
    d5 = len(df[f5 & (df['peak'] >= 30.0)])
    print(f"{'V-STRIKE (ATR>6, Vol>0.7)':<40} | {len(df[f5]):<10} | %{(d5/total_d)*100:<13.1f} | %{(d5/len(df[f5]))*100:.2f}")

if __name__ == "__main__":
    compare_filters()
