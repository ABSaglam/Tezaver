#!/usr/bin/env python3
"""
YESİL LISTE OPERASYONU: FAZ 1 - HAZIRLIK
=======================================
1. 'refined_global_report_v17.md' raporunu okur.
2. Koin bazlı kazanma oranlarını hesaplar.
3. WR < %30 olanları 'data/blacklist_green.json' dosyasına yazar.
4. Blacklist haricindeki koinleri 'refined_global_report_green_CLEANED.md' olarak kaydeder (Kural üretimi için).
"""

import pandas as pd
import json
import os
import re

REPORT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_v17.md"
BLACKLIST_FILE = "/Users/alisaglam/TezaverMac/data/blacklist_green.json"
CLEAN_REPORT = "/Users/alisaglam/TezaverMac/refined_global_report_green_CLEANED.md"

def analyze_and_clean():
    print(f"--- YEŞİL LİSTE ANALİZİ BAŞLIYOR ---")
    
    with open(REPORT_FILE, "r") as f:
        lines = f.readlines()
        
    data = []
    
    for line in lines:
        if not line.strip().startswith("|") or "---" in line or "NO" in line: continue
        
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 15: continue
        
        # Parse basic info
        sym = parts[2].strip()
        if not sym or sym == "SYM": continue
        
        tier_raw = parts[14].strip()
        if "💎" in tier_raw: tier = "Diamond"
        elif "🥇" in tier_raw: tier = "Gold"
        elif "🥈" in tier_raw: tier = "Silver"
        elif "🥉" in tier_raw: tier = "Bronze"
        else: tier = "NoTier"
        
        is_success = tier != "NoTier"
        
        data.append({
            "line": line, # Keep original line for writing back
            "symbol": sym,
            "success": is_success
        })
        
    df = pd.DataFrame(data)
    if df.empty:
        print("HATA: Veri bulunamadı!")
        return

    # 1. Generate Blacklist
    all_coins = df['symbol'].unique()
    blacklist = []
    
    print(f"\n📊 Koin Performans Analizi ({len(all_coins)} Koin):")
    
    for sym in all_coins:
        sub = df[df['symbol'] == sym]
        total = len(sub)
        wins = sub['success'].sum()
        wr = (wins / total) * 100
        
        # Blacklist Criteria: WR < 30% or (Total > 10 and WR < 40%)
        # Keeping it strict: < 30% is toxic.
        
        if wr < 30:
            blacklist.append(sym)
            # print(f"  ❌ {sym}: %{wr:.1f} ({wins}/{total}) -> BLACKLIST")
            
    print(f"\n⚠️ Toplam {len(blacklist)} Zehirli Koin Tespit Edildi.")
    
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(blacklist, f, indent=4)
    print(f"✅ Blacklist kaydedildi: {BLACKLIST_FILE}")
    
    # 2. Creates Clean Report
    clean_lines = []
    # Add Header (Assume standard header)
    clean_lines.append(lines[0])
    clean_lines.append(lines[1])
    
    # Find header row index
    header_idx = 0
    for i, l in enumerate(lines):
        if "| NO | SYM |" in l:
            header_idx = i
            clean_lines.append(l)
            clean_lines.append(lines[i+1]) # Separator
            break
            
    # Add filtered rows
    dropped_count = 0
    for d in data:
        if d['symbol'] not in blacklist:
            clean_lines.append(d['line'])
        else:
            dropped_count += 1
            
    with open(CLEAN_REPORT, "w") as f:
        f.write("".join(clean_lines))
        
    print(f"✅ Temiz Rapor Hazırlandı: {CLEAN_REPORT}")
    print(f"   - Orijinal Sinyal: {len(data)}")
    print(f"   - Atılan Sinyal: {dropped_count}")
    print(f"   - Kalan Sinyal: {len(data) - dropped_count}")

if __name__ == "__main__":
    analyze_and_clean()
