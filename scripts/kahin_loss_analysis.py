import pandas as pd
import numpy as np

FILE = "/Users/alisaglam/TezaverMac/kahin_discovery_results.csv"

def analyze_loss():
    df = pd.read_csv(FILE)
    
    # 🏛️ TIER DEFINITIONS
    diamonds = df[df['peak'] >= 30.0]
    golds = df[(df['peak'] >= 20.0) & (df['peak'] < 30.0)]
    silvers = df[(df['peak'] >= 10.0) & (df['peak'] < 20.0)]
    
    total_d = len(diamonds)
    total_g = len(golds)
    total_s = len(silvers)
    
    # 🏛️ PROPOSED FILTER
    f_cond = (df['btc_ok'] == 1) & (df['rsi_d'] > 60) & (df['vol_mom'] > 1.0)
    filtered_df = df[f_cond]
    
    caught_d = len(filtered_df[filtered_df['peak'] >= 30.0])
    caught_g = len(filtered_df[(filtered_df['peak'] >= 20.0) & (filtered_df['peak'] < 30.0)])
    caught_s = len(filtered_df[(filtered_df['peak'] >= 10.0) & (filtered_df['peak'] < 20.0)])
    
    print("🏛️ KAHİN: TIER KAYIP ANALİZİ (2023-2025)")
    print("-" * 40)
    print(f"Toplam Elmas (>=30%): {total_d}")
    print(f"Filtreye Takılan Elmas: {caught_d} (%{(caught_d/total_d)*100:.1f} Başarı)")
    print(f"KAYIP ELMAS: {total_d - caught_d} (%{((total_d - caught_d)/total_d)*100:.1f})")
    print("-" * 40)
    print(f"Toplam Altın (>=20%): {total_g}")
    print(f"Filtreye Takılan Altın: {caught_g} (%{(caught_g/total_g)*100:.1f} Başarı)")
    print(f"KAYIP ALTIN: {total_g - caught_g} (%{((total_g - caught_g)/total_g)*100:.1f})")
    print("-" * 40)
    print(f"Toplam Gümüş (>=10%): {total_s}")
    print(f"Filtreye Takılan Gümüş: {caught_s} (%{(caught_s/total_s)*100:.1f} Başarı)")
    print(f"KAYIP GÜMÜŞ: {total_s - caught_s} (%{((total_s - caught_s)/total_s)*100:.1f})")
    print("-" * 40)
    
    # 🏛️ EFFICIENCY CHECK
    total_days = len(df)
    filtered_days = len(filtered_df)
    print(f"Toplam İzlenen Gün Sayısı: {total_days}")
    print(f"Filtre Sonrası Kalan Gün: {filtered_days} (İş Yükü %{ (filtered_days/total_days)*100:.1f} Azaldı)")
    print(f"Her 100 günde yakalanan Elmas (Baz): {(total_d/total_days)*100:.2f}")
    print(f"Her 100 günde yakalanan Elmas (Filtre): {(caught_d/filtered_days)*100:.2f}")

if __name__ == "__main__":
    analyze_loss()
