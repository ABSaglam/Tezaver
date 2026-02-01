#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2: FAZ 4 - FİLTRELENMİŞ TIER ANALİZİ (OLACAK)
==========================================================
Faz 1 (tarihsel scan) ve Faz 3 (golden keys) verilerini birleştir.
Sadece Golden DNA ile eşleşen tetikleri filtrele.
Yeni tier dağılımını ve başarı oranlarını hesapla.
"""

import pandas as pd
import os
import json

SCAN_FILE = "/Users/alisaglam/TezaverMac/data/ayas2_historical_scan.parquet"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_v2"

def analyze_filtered():
    print("=" * 60)
    print("AYAŞ TÜNELİ-2: FAZ 4 - FİLTRELENMİŞ ANALİZ")
    print("=" * 60)
    
    if not os.path.exists(SCAN_FILE):
        print("HATA: Scan dosyası yok.")
        return

    df = pd.read_parquet(SCAN_FILE)
    print(f"Toplam Tetik (Ham): {len(df)}")
    
    # Golden Keys yükle
    golden_map = {}
    key_files = [f for f in os.listdir(KEYS_DIR) if f.endswith("_key.json")]
    
    for kf in key_files:
        try:
            with open(os.path.join(KEYS_DIR, kf), "r") as f:
                data = json.load(f)
                symbol = data['symbol']
                dna_list = set(data['golden_dna_list'])
                golden_map[symbol] = dna_list
        except: pass
        
    print(f"Yüklenen Golden Anahtar: {len(golden_map)}")
    
    # Filtreleme
    filtered_results = []
    
    for idx, row in df.iterrows():
        sym = row['symbol']
        dna = row['dna']
        
        if sym in golden_map:
            if dna in golden_map[sym]:
                filtered_results.append(row)
                
    filtered_df = pd.DataFrame(filtered_results)
    
    if filtered_df.empty:
        print("Filtre sonrası hiç veri kalmadı!")
        return
        
    print(f"\nFiltre Sonrası Tetik: {len(filtered_df)}")
    print(f"Elenme Oranı: %{(1 - len(filtered_df)/len(df))*100:.1f}")
    
    # --- ANALİZ ---
    print("\n📊 FİLTRELENMİŞ PERFORMANS (OLACAK)")
    print("-" * 40)
    print(f"Ortalama MAX: +{filtered_df['max_pct'].mean():.2f}%")
    print(f"Ortalama CLOSE: {filtered_df['close_pct'].mean():+.2f}%")
    
    # Tier dağılımı
    print("\n🏆 TIER DAĞILIMI (FİLTRELİ)")
    print("-" * 40)
    tier_counts = filtered_df['tier'].value_counts()
    tier_order = ['Diamond', 'Gold', 'Silver', 'Bronze', 'NoTier']
    tier_icons = {'Diamond': '💎', 'Gold': '🥇', 'Silver': '🥈', 'Bronze': '🥉', 'NoTier': '-'}
    
    for tier in tier_order:
        count = tier_counts.get(tier, 0)
        pct = (count / len(filtered_df)) * 100
        print(f"  {tier_icons[tier]} {tier:8s}: {count:5d}  ({pct:5.1f}%)")
    
    # Başarı oranı
    success_count = len(filtered_df[filtered_df['tier'].isin(['Diamond', 'Gold', 'Silver', 'Bronze'])])
    success_pct = (success_count / len(filtered_df)) * 100
    
    print(f"\n  ✅ Başarılı (≥Bronze): {success_count} ({success_pct:.1f}%)")
    print(f"  ❌ Başarısız (NoTier): {len(filtered_df) - success_count} ({100 - success_pct:.1f}%)")
    
    # Karşılaştırma
    print("\n⚖️ GELİŞİM RAPORU")
    print("-" * 40)
    raw_success_pct = 6.5 # Faz 1'den
    improvement = success_pct / raw_success_pct
    print(f"Başarı Oranı: %{raw_success_pct:.1f} -> %{success_pct:.1f} ({improvement:.1f}x İyileşme)")

if __name__ == "__main__":
    analyze_filtered()
