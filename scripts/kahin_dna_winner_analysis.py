import pandas as pd
import numpy as np

FILE = "/Users/alisaglam/TezaverMac/rally_dna_audit_results.csv"

def analyze_winning_dna():
    df = pd.read_csv(FILE)
    
    # 🏛️ SEGMENT BY PEAK STRENGTH
    diamonds = df[df['peak'] >= 30.0]
    golds = df[(df['peak'] >= 20.0) & (df['peak'] < 30.0)]
    silvers = df[(df['peak'] >= 10.0) & (df['peak'] < 20.0)]
    
    metrics = ['rsi_val', 'rsi_ang', 'v_mom', 'vol_avg_past', 'dist_rib', 'tr_p']
    
    print("🏛️ KAHİN: RALLY DNA ANALİZİ (2023-2025)")
    print("=" * 60)
    
    for tier_name, tier_df in [("ELMAS (>=30%)", diamonds), ("ALTIN (>=20%)", golds), ("GÜMÜŞ (>=10%)", silvers)]:
        print(f"\n💎 {tier_name} - Örnek: {len(tier_df)}")
        for m in metrics:
            print(f"{m:<15} | Median: {tier_df[m].median():.2f} | 75th: {tier_df[m].quantile(0.75):.2f}")
        print("-" * 30)

    # 🏛️ THE "SUPERNOVA" SIGNATURE (High Volume + High Angle)
    supernova = df[(df['v_mom'] > 2.0) & (df['rsi_ang'] > 45.0)]
    print(f"\n🚀 SUPERNOVA DNA ADAYI (VolMom > 2.0 & RSI Ang > 45°)")
    print(f"Örnek Sayısı: {len(supernova)}")
    print(f"Ortalama Kâr: %{supernova['peak'].mean():.2f}")
    if not supernova.empty:
        print(f"Elmas Getirme Oranı: %{(len(supernova[supernova['peak']>=30]) / len(supernova))*100:.1f}")

if __name__ == "__main__":
    analyze_winning_dna()
