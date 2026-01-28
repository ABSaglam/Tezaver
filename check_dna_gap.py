
import json
import os
import pandas as pd
from tezaver.engines.tunnel_engine import TunnelEngine

def check_dna_gap():
    engine = TunnelEngine()
    target_date = "2026-01-28"
    test_coins = ["BTCUSDT", "SOLUSDT", "ETHUSDT"]
    
    print("--- 🔍 DNA EŞLEŞME ANALİZİ (DERİN BAKIŞ) ---")
    
    for symbol in test_coins:
        print(f"\n[{symbol}]")
        
        # 1. Get Live DNA
        has_perm, status, live_dna = engine.check_permission(symbol, target_date)
        print(f"Canlı DNA: {live_dna}")
        
        # 2. Get Golden Keys
        key_path = os.path.join(engine.golden_keys_dir, f"{symbol}_key.json")
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                key_data = json.load(f)
                golden_dnas = key_data.get('golden_dna_list', [])
                print(f"Altın DNA Sayısı: {len(golden_dnas)}")
                
                # Check for "Near Matches" (same 5 out of 6 components)
                live_parts = live_dna.split('|')
                print("Benzerlik Kontrolü (5/6 Eşleşme):")
                found_near = False
                for g_dna in golden_dnas:
                    g_parts = g_dna.split('|')
                    matches = sum(1 for l, g in zip(live_parts, g_parts) if l == g)
                    if matches >= 5:
                        print(f" -> Yakın DNA: {g_dna} ({matches}/6)")
                        found_near = True
                if not found_near:
                    print(" -> Yakın eşleşme bile yok. Formasyon tamamen farklı.")
        else:
            print("❌ Altın Anahtar bulunamadı.")

if __name__ == "__main__":
    check_dna_gap()
