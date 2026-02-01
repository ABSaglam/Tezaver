#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2: EVRENSEL DNA ÇIKARIMI (LIST-2)
==============================================
Faz 1 sonuçlarını (ayas2_historical_scan.parquet) kullanır.
TÜM koinler için (başarısız olanlar dahil) en iyi performansı gösteren DNA'ları bulur.
- Amac: Hiç kazanamayan koine bile bir "Anahtar" vermek (En az kötü olanı).
- Çıktı: `data/golden_keys_list2/*.json`
"""

import pandas as pd
import os
import json
from datetime import datetime

SCAN_FILE = "/Users/alisaglam/TezaverMac/data/ayas2_historical_scan.parquet"
OUTPUT_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_list2"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def extract_universal_dna():
    print("=" * 60)
    print("AYAŞ TÜNELİ-2: EVRENSEL DNA ÇIKARIMI (LIST-2)")
    print("=" * 60)
    
    if not os.path.exists(SCAN_FILE):
        print(f"HATA: Tarama dosyası bulunamadı: {SCAN_FILE}")
        return

    df = pd.read_parquet(SCAN_FILE)
    print(f"Toplam Veri: {len(df)}")
    
    # Coin bazlı grupla
    grouped = df.groupby('symbol')
    
    total_coins = 0
    
    for symbol, group in grouped:
        # Bu coin için DNA başarı analizi yap
        dna_stats = {}
        
        for dna, sub_df in group.groupby('dna'):
            if dna == "neutral": continue
            
            count = len(sub_df)
            # Başarı: Bronze ve üzeri
            wins = len(sub_df[sub_df['tier'].isin(['Diamond', 'Gold', 'Silver', 'Bronze'])])
            win_rate = (wins / count) * 100
            avg_return = sub_df['max_pct'].mean()
            
            dna_stats[dna] = {
                'count': count,
                'wins': wins,
                'win_rate': win_rate,
                'avg_return': avg_return
            }
        
        if not dna_stats:
            continue
            
        # Sıralama Algoritması:
        # 1. Kazanma Oranı (%WR)
        # 2. Ortalama Getiri (Avg Ret)
        # 3. Frekans (Count)
        sorted_dnas = sorted(
            dna_stats.items(), 
            key=lambda x: (x[1]['win_rate'], x[1]['avg_return'], x[1]['count']), 
            reverse=True
        )
        
        # En iyi 3 DNA'yı seç (veya hiç yoksa en sık görüleni)
        # Kurallar:
        # - Eğer hiç kazanan yoksa (WR=0), "En Az Zarar Ettiren" (Avg Ret) seçilir.
        top_dnas = [item[0] for item in sorted_dnas[:5]] # Top 5 alalım şimdilik
        
        # Kaydet
        key_data = {
            "symbol": symbol,
            "list_type": "universal_list_2",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_triggers_analyzed": len(group),
            "best_dna_stats": {d: dna_stats[d] for d in top_dnas},
            "golden_dna_list": top_dnas
        }
        
        with open(f"{OUTPUT_DIR}/{symbol}_key.json", "w") as f:
            json.dump(key_data, f, indent=2)
            
        total_coins += 1
        
    print("\n" + "=" * 60)
    print("✅ EVRENSEL LİSTE OLUŞTURULDU")
    print("=" * 60)
    print(f"Anahtar Oluşturulan Coin: {total_coins}")
    print(f"Klasör: {OUTPUT_DIR}")

if __name__ == "__main__":
    extract_universal_dna()
