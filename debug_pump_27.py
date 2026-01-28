
import json
import os
import pandas as pd
from tezaver.engines.tunnel_engine import TunnelEngine

def debug_pump_27():
    engine = TunnelEngine()
    symbol = "PUMPUSDT"
    target_date = "2026-01-27"
    
    print(f"--- 🧬 PUMPUSDT DNA ANALİZİ (27 OCAK) ---")
    
    # 1. Get Live DNA for 27th
    # check_permission internally looks at target_date - 1 day (26th) for DNA
    has_perm, status, live_dna = engine.check_permission(symbol, target_date)
    print(f"Canlı DNA (Hesaplanan): {live_dna}")
    print(f"Vize Durumu: {status}")
    
    # 2. Inspect Golden Key
    key_path = os.path.join(engine.golden_keys_dir, f"{symbol}_key.json")
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            key_data = json.load(f)
            golden_dnas = key_data.get('golden_dna_list', [])
            print(f"Altın Anahtardaki DNA Sayısı: {len(golden_dnas)}")
            
            if live_dna in golden_dnas:
                print("✅ EŞLEŞME VAR! (Neden 0 çıktı?)")
            else:
                print("❌ EŞLEŞME YOK.")
                # Show differences with the first golden DNA
                if golden_dnas:
                    print(f"Örnek Altın DNA: {golden_dnas[0]}")
    else:
        print("❌ Golden Key bulunamadı.")

if __name__ == "__main__":
    debug_pump_27()
