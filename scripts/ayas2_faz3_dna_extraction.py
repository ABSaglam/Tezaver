#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2: FAZ 3 - DNA ÇIKARIMI
====================================
Faz 1 sonuçlarını (ayas2_historical_scan.parquet) analiz et.
Her coin için başarılı (Bronze+) tetiklerin DNA'larını topla.
Frekansı >= 3 olan DNA'ları "golden_keys_v2/{SYMBOL}_key.json" olarak kaydet.
"""

import pandas as pd
import os
import json
from datetime import datetime

SCAN_FILE = "/Users/alisaglam/TezaverMac/data/ayas2_historical_scan.parquet"
OUTPUT_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_v2"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def extract_dna():
    print("=" * 60)
    print("AYAŞ TÜNELİ-2: FAZ 3 - DNA ÇIKARIMI")
    print("=" * 60)
    
    if not os.path.exists(SCAN_FILE):
        print(f"HATA: Tarama dosyası bulunamadı: {SCAN_FILE}")
        return

    df = pd.read_parquet(SCAN_FILE)
    print(f"Toplam Tetik: {len(df)}")
    
    # Başarılıları filtrele (Bronze ve üzeri)
    success_tiers = ['Diamond', 'Gold', 'Silver', 'Bronze']
    success_df = df[df['tier'].isin(success_tiers)]
    print(f"Başarılı Tetik (Bronze+): {len(success_df)}")
    
    # Coin bazlı grupla
    grouped = success_df.groupby('symbol')
    
    total_coins = 0
    total_dna = 0
    min_freq = 3  # En az 3 kez görülmeli (kullanıcı onayıyla)
    
    for symbol, group in grouped:
        # DNA frekans analizi
        dna_counts = group['dna'].value_counts()
        
        # Filtrele: Neutral olmayan ve frekansı >= 3 olanlar
        valid_dna = []
        for dna, count in dna_counts.items():
            if dna == "neutral": continue
            if count >= min_freq:
                valid_dna.append(dna)
        
        if not valid_dna:
            continue
            
        # Kaydet
        key_data = {
            "symbol": symbol,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system_version": "ayas_v2",
            "min_freq": min_freq,
            "total_success_triggers": len(group),
            "golden_dna_count": len(valid_dna),
            "golden_dna_list": valid_dna
        }
        
        with open(f"{OUTPUT_DIR}/{symbol}_key.json", "w") as f:
            json.dump(key_data, f, indent=2)
            
        total_coins += 1
        total_dna += len(valid_dna)
        
    print("\n" + "=" * 60)
    print("✅ FAZ 3 TAMAMLANDI")
    print("=" * 60)
    print(f"Golden Anahtar Oluşturulan Coin: {total_coins}")
    print(f"Toplam Golden DNA Sayısı: {total_dna}")
    print(f"Dosyalar: {OUTPUT_DIR}/*.json")

if __name__ == "__main__":
    extract_dna()
