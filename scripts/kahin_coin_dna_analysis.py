import pandas as pd
import numpy as np

FILE = "/Users/alisaglam/TezaverMac/rally_dna_audit_results.csv"

def analyze_coin_specific_dna():
    df = pd.read_csv(FILE)
    
    # 🏛️ COIN ODAKLI AGREGASYON
    # Sadece anlamlı sayıda rallisi olan koinleri alalım (İstatistiksel güven)
    coin_stats = df.groupby('symbol').agg({
        'peak': ['count', 'mean', 'median'],
        'rsi_ang': 'median',
        'v_mom': 'median',
        'tr_p': 'median'
    })
    
    # Flatten columns
    coin_stats.columns = ['_'.join(col).strip() for col in coin_stats.columns.values]
    
    # Rename for clarity
    coin_stats = coin_stats.rename(columns={
        'peak_count': 'Rally_Count',
        'peak_mean': 'Avg_Gain',
        'peak_median': 'Median_Gain',
        'rsi_ang_median': 'DNA_Ang',
        'v_mom_median': 'DNA_Vol',
        'tr_p_median': 'DNA_ATR'
    })
    
    # Filter for coins with >= 20 rallies for reliability
    reliable_coins = coin_stats[coin_stats['Rally_Count'] >= 20].sort_values('DNA_Vol', ascending=False)
    
    print("🏛️ KAHİN: KOİN-SPESİFİK DNA KARAKTERLERİ (2023-2025)")
    print("-" * 80)
    print(reliable_coins.head(30)) # Top 30 highest volume DNA coins
    
    # 🏛️ VARIANCE ANALYSIS
    print("-" * 80)
    print(f"DNA_Ang (RSI Açısı) Varyansı: Min {reliable_coins['DNA_Ang'].min():.1f}° | Max {reliable_coins['DNA_Ang'].max():.1f}°")
    print(f"DNA_Vol (Hacim Mom) Varyansı: Min {reliable_coins['DNA_Vol'].min():.1f}x | Max {reliable_coins['DNA_Vol'].max():.1f}x")
    print("-" * 80)
    
    # Save as a Coin Manifest
    reliable_coins.to_csv("/Users/alisaglam/TezaverMac/kahin_coin_dna_manifest.csv")
    print(f"✅ Koin-Spesifik DNA Manifesti kaydedildi: /Users/alisaglam/TezaverMac/kahin_coin_dna_manifest.csv")

if __name__ == "__main__":
    analyze_coin_specific_dna()
