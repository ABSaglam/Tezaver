
import os
import json
import pandas as pd
from tezaver.engines.tunnel_engine import TunnelEngine
from tezaver.core.config import COIN_CELLS_DIR

def run_phase_a_audit():
    target_date_str = "2026-01-28"
    print(f"--- 🔬 AYAŞ TÜNELİ (FAZ A) DERİN DENETİM - {target_date_str} ---")
    
    engine = TunnelEngine()
    
    # Get all symbols
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    symbols.sort()
    
    granted_coins = []
    denied_count = 0
    missing_key_count = 0
    error_count = 0
    
    print(f"Başlatılıyor: {len(symbols)} varlık kontrol edilecek.")
    
    for i, symbol in enumerate(symbols):
        if i % 100 == 0:
            print(f"İşleniyor: {i}/{len(symbols)}...", flush=True)
            
        try:
            has_perm, status, dna = engine.check_permission(symbol, target_date_str)
            
            if has_perm:
                granted_coins.append({"symbol": symbol, "dna": dna})
            elif status == "NO_KEY":
                missing_key_count += 1
            elif status.startswith("ERROR"):
                error_count += 1
            else:
                denied_count += 1
                
        except Exception as e:
            error_count += 1
            
    print("\n" + "="*40)
    print(f"📊 DENETİM ÖZETİ ({target_date_str})")
    print("="*40)
    print(f"✅ AYAŞ TÜNELİ'NDEN GEÇENLER: {len(granted_coins)}")
    print(f"❌ REDDEDİLENLER (Uyumsuz DNA): {denied_count}")
    print(f"⚠️ ALTIN ANAHTARI OLMAYANLAR: {missing_key_count}")
    print(f"🔥 SİSTEM HATASI: {error_count}")
    print("="*40)
    
    if granted_coins:
        print("\n📝 VİZE ALANLAR:")
        # Display in a compact format
        for res in granted_coins:
            print(f"- {res['symbol']}")
    else:
        print("\n⛔ HİÇBİR KOİN VİZE ALAMADI.")

if __name__ == "__main__":
    run_phase_a_audit()
