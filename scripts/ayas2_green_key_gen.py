#!/usr/bin/env python3
"""
YESİL LİSTE: ANAHTAR YENİLEME (v3)
==================================
Eski Yeşil Liste (v2) koinleri için "Universal Key" mantığıyla
yepyeni, optimize edilmiş anahtarlar üretir.
Girdi: golden_keys_v2 (Listeyi almak için), ayas2_historical_scan.parquet
Çıktı: golden_keys_green_v3
"""

import pandas as pd
import os
import json
from datetime import datetime

SCAN_FILE = "/Users/alisaglam/TezaverMac/data/ayas2_historical_scan.parquet"
OLD_KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_v2"
OUTPUT_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_green_v3"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def regenerate_green_keys():
    print("YESİL LİSTE REBIRTH (v3 Key Gen)")
    print("=" * 60)
    
    # 1. Get Target Coins
    green_coins = set()
    if os.path.exists(OLD_KEYS_DIR):
        for f in os.listdir(OLD_KEYS_DIR):
            if f.endswith("_key.json"):
                green_coins.add(f.replace("_key.json", ""))
    
    print(f"Hedef Koin Sayısı: {len(green_coins)}")
    
    # 2. Load Scan Data
    if not os.path.exists(SCAN_FILE):
        print("HATA: Parquet dosyası yok!")
        return
        
    df = pd.read_parquet(SCAN_FILE)
    print(f"Toplam Tarama Verisi: {len(df)}")
    
    # 3. Generate Keys
    grouped = df.groupby('symbol')
    generated_count = 0
    
    for symbol, group in grouped:
        if symbol not in green_coins: continue
        
        dna_stats = {}
        for dna, sub_df in group.groupby('dna'):
            if dna == "neutral": continue
            
            count = len(sub_df)
            wins = len(sub_df[sub_df['tier'].isin(['Diamond', 'Gold', 'Silver', 'Bronze'])])
            win_rate = (wins / count) * 100
            avg_return = sub_df['max_pct'].mean()
            
            dna_stats[dna] = {
                'count': count,
                'wins': wins,
                'win_rate': win_rate,
                'avg_return': avg_return
            }
            
        if not dna_stats: continue
        
        # Sort best DNA
        sorted_dnas = sorted(
            dna_stats.items(), 
            key=lambda x: (x[1]['win_rate'], x[1]['avg_return']), 
            reverse=True
        )
        
        top_dnas = [item[0] for item in sorted_dnas[:5]] # Top 5
        
        key_data = {
            "symbol": symbol,
            "list_type": "green_list_v3",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_triggers": len(group),
            "best_dna_stats": {d: dna_stats[d] for d in top_dnas},
            "golden_dna_list": top_dnas
        }
        
        with open(f"{OUTPUT_DIR}/{symbol}_key.json", "w") as f:
            json.dump(key_data, f, indent=2)
            
        generated_count += 1
        
    print(f"✅ Yeni Anahtar Üretildi: {generated_count}")
    print(f"📂 Klasör: {OUTPUT_DIR}")

if __name__ == "__main__":
    regenerate_green_keys()
