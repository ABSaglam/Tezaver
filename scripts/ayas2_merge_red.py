#!/usr/bin/env python3
"""
KIRMIZI LİSTE: BÜYÜK BİRLEŞME
=============================
Girdi 1: SARI_LISTE_FINAL.md (List-2 Optimized)
Girdi 2: YESIL_LISTE_V3_FINAL.md (Green V3 Optimized)
Çıktı: KIRMIZI_LISTE_FINAL.md
İşlem: Satırları birleştir, tarihe göre sırala, istatistikleri hesapla.
"""

import pandas as pd
import os
from datetime import datetime

FILE_YELLOW = "/Users/alisaglam/TezaverMac/SARI_LISTE_FINAL.md"
FILE_GREEN = "/Users/alisaglam/TezaverMac/YESIL_LISTE_V3_FINAL.md"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/KIRMIZI_LISTE_FINAL.md"

def parse_md_file(path, source_tag):
    rows = []
    try:
        with open(path, "r") as f:
            lines = f.readlines()
            
        for line in lines:
            if not line.strip().startswith("|") or "---" in line or "NO" in line: continue
            
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 15: continue
            
            # Extract Date for Sorting (Col 5 usually)
            # Format: 2024-10-23 14:15
            date_str = parts[5]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except:
                dt = datetime.min
                
            # Tier Extraction
            tier_raw = parts[14]
            if "💎" in tier_raw: tier = "Diamond"
            elif "🥇" in tier_raw: tier = "Gold"
            elif "🥈" in tier_raw: tier = "Silver"
            elif "🥉" in tier_raw: tier = "Bronze"
            else: tier = "NoTier"
            
            # Tag the row source (Optional, or just merge)
            # Maybe append a column? Or just keep as is.
            # User just wants a merged list.
            
            rows.append({
                "line": line.strip(),
                "dt": dt,
                "tier": tier,
                "source": source_tag
            })
            
    except Exception as e: print(f"Hata ({path}): {e}")
    return rows

def merge_lists():
    print("🔴 KIRMIZI LİSTE OPERASYONU BAŞLIYOR...")
    
    yellow_rows = parse_md_file(FILE_YELLOW, "SARI")
    green_rows = parse_md_file(FILE_GREEN, "YEŞİL")
    
    print(f"🟡 Sarı Sinyal: {len(yellow_rows)}")
    print(f"🟢 Yeşil Sinyal: {len(green_rows)}")
    
    all_rows = yellow_rows + green_rows
    
    # Sort by Date
    all_rows.sort(key=lambda x: x['dt'])
    
    print(f"🔴 Toplam Sinyal: {len(all_rows)}")
    
    # Stats
    tiers = {"Diamond": 0, "Gold": 0, "Silver": 0, "Bronze": 0, "NoTier": 0}
    for r in all_rows:
        tiers[r['tier']] += 1
        
    total = len(all_rows)
    success = total - tiers["NoTier"]
    rate = (success / total) * 100 if total > 0 else 0
    
    print("-" * 40)
    print(f"📊 BİRLEŞİK BAŞARI: %{rate:.2f}")
    print(f"💎 Diamond: {tiers['Diamond']}")
    print(f"🥇 Gold:    {tiers['Gold']}")
    print(f"❌ NoTier:  {tiers['NoTier']}")
    print("-" * 40)
    
    # Write File
    with open(OUTPUT_FILE, "w") as f:
        f.write("# KIRMIZI LİSTE (THE RED LIST - MASTER FUSION)\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Sources: Sarı ({len(yellow_rows)}) + Yeşil ({len(green_rows)})\n")
        f.write("| NO | SYM | MAX | CLOSE | TIME | SIGNAL | CONVICTION | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        
        for idx, r in enumerate(all_rows):
            parts = [p.strip() for p in r['line'].split("|")]
            # parts expected structure: ['', 'NO', 'SYM', ..., 'VMOM', ''] (if ends with |)
            
            # Construct new cleaner list
            # Skip empty first and last if exist
            clean_parts = [p for p in parts if p != '']
            
            # If we merged successfully, clean_parts[0] should be old NO, clean_parts[1] SYM etc.
            # But wait, original has | NO | ...
            # split("|") -> ['', 'NO', ...]
            
            if len(clean_parts) < 20: 
                # Fallback
                f.write(r['line'] + "\n")
                continue
                
            clean_parts[0] = str(idx + 1)
            
            # Ensure V-Mom has 'x'
            # (It usually does)
            
            # Rebuild properly
            new_line = "| " + " | ".join(clean_parts) + " |"
            f.write(new_line + "\n")
                
    print(f"✅ Kırmızı Liste Oluşturuldu: {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_lists()
