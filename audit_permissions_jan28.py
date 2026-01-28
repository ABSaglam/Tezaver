
from tezaver.engines.tunnel_engine import TunnelEngine
import os
import json

def audit_permissions():
    print("--- 28 OCAK TÜNEL GİRİŞ İZNİ DENETİMİ ---")
    
    engine = TunnelEngine()
    date_str = "2026-01-28"
    
    # Get all symbols
    symbols = [d for d in os.listdir(engine.cells_dir) if os.path.isdir(os.path.join(engine.cells_dir, d))]
    symbols.sort()
    
    granted = []
    denied = []
    missing_key = []
    error = []

    print(f"Toplam Varlık: {len(symbols)}")
    print("Denetim Başladı...", end="", flush=True)

    for i, symbol in enumerate(symbols):
        if i % 50 == 0: print(".", end="", flush=True)
        
        try:
            has_perm, status, dna = engine.check_permission(symbol, date_str)
            
            if has_perm:
                granted.append((symbol, dna))
            elif status == "NO_KEY":
                missing_key.append(symbol)
            elif status.startswith("ERROR"):
                error.append(symbol)
            else:
                denied.append(symbol)
                
        except Exception as e:
            error.append(symbol)

    print("\n\n📊 DENETİM SONUCU:")
    print(f"✅ İZİN VERİLEN (Tünele Girenler): {len(granted)}")
    print(f"❌ REDDEDİLEN (DNA Uyumsuz): {len(denied)}")
    print(f"⚠️ ANAHTAR YOK: {len(missing_key)}")
    print(f"🔥 HATA: {len(error)}")
    
    if granted:
        print("\n🦅 TÜNELE GİRMEYE HAK KAZANANLAR (Takip Listesi):")
        for sym, dna in granted:
            print(f"- {sym} (DNA: {dna})")
    else:
        print("\n⛔ KİMSE GİREMEDİ. (Bugün hiçbir coin Golden Key DNA'sı ile eşleşmedi)")
        print("Piyasa tamamen formasyon dışı.")

if __name__ == "__main__":
    audit_permissions()
