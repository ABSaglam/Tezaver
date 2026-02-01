#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2: BAŞARISIZLIK ANALİZİ ROBOTU (FAZ 2: KOİN BAZLI ETKİ)
===================================================================
Hedef: "Müjde Filtresi"nin (Trend+Val+Map) her koin üzerindeki bireysel etkisini ölçmek.
Genel iyileşme koin bazında bir yıkıma (Elmas kaybına) neden oluyor mu?

Veri Kaynağı: refined_global_report_list2_CLEANED.md (Blacklist uygulanmış hali)
"""

import re
import pandas as pd
import numpy as np
import json

# NOT: Artık temizlenmiş raporu kullanıyoruz
REPORT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_list2_CLEANED.md"

def parse_report():
    print(f"Rapor okunuyor: {REPORT_FILE}")
    
    with open(REPORT_FILE, "r") as f:
        lines = f.readlines()
        
    data = []
    
    for line in lines:
        if not line.strip().startswith("|"): continue
        if "---" in line or "NO" in line and "SYM" in line: continue
        
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 20: continue # Invalid line
        
        # Initialize defaults
        max_val=0; angle=0; adx=0; atr=0; vmom=0; hour=0
        t4="Neutral"; t1="Neutral"; trend_score="Mixed"; pos_val="Neutral"; val_type="Normal"

        try:
            # 1. Parsing SYM (Symbol)
            sym = parts[2].strip()
            
            # 2. Parsing TIER (Success Label)
            tier_raw = parts[14].strip()
            if "💎" in tier_raw: tier_label = "Diamond"
            elif "🥇" in tier_raw: tier_label = "Gold"
            elif "🥈" in tier_raw: tier_label = "Silver"
            elif "🥉" in tier_raw: tier_label = "Bronze"
            else: tier_label = "NoTier"
            
            is_success = tier_label != "NoTier"
            is_diamond = tier_label == "Diamond"
            
            # 3. Parsing MAX (Numeric)
            max_raw = parts[3].replace("<font color='green'>", "").replace("<font color='red'>", "").replace("</font>", "").replace("**", "").replace("%", "").replace("+", "").strip()
            if max_raw: max_val = float(max_raw)
            else: max_val = 0
            
            # 4. Parsing TREND (4H | 1H) -> 🟢🔴
            trend_raw = parts[8].strip()
            t4 = "Bull" if "🟢" in trend_raw[0:1] else "Bear"
            t1 = "Bull" if "🟢" in trend_raw[-1] else "Bear" 
            
            if trend_raw.count("🟢") == 2: trend_score = "Bull/Bull"
            elif trend_raw.count("🔴") == 2: trend_score = "Bear/Bear"
            else: trend_score = "Mixed"

            # 5. Parsing POS (Context)
            pos_raw = parts[9].strip()
            if "🟢" in pos_raw: pos_val = "Bullish"
            elif "🔴" in pos_raw: pos_val = "Bearish"
            else: pos_val = "Neutral"

            # 6. Parsing VAL (Squeeze/Value)
            val_raw = parts[12].strip()
            if "💚" in val_raw: val_type = "Squeeze" # Green Heart
            elif "❤️" in val_raw: val_type = "Danger"
            else: val_type = "Normal"

            # 7. ADX
            adx_raw = parts[20]
            adx_clean = re.sub(r"[^0-9.]", "", adx_raw)
            adx = float(adx_clean) if adx_clean else 0
            
            # 8. V-Mom (X temizliği dahil)
            vmom_raw = parts[26]
            vmom_clean = vmom_raw.lower().replace("x", "").strip()
            if vmom_clean:
                 vmom = float(vmom_clean)
            else:
                 vmom = 0.0

            # Time parsing if needed
            time_str = parts[5].strip()
            if ":" in time_str: hour = int(time_str.split(":")[0])
            else: hour = 0
            
            data.append({
                "symbol": sym,
                "tier": tier_label,
                "success": is_success,
                "is_diamond": is_diamond,
                "trend_score": trend_score,
                "val_type": val_type,
                "vmom": vmom,
                "adx": adx
            })
            
        except Exception as e:
            continue

    return pd.DataFrame(data)

def analyze_filter_impact_per_coin(df):
    print("\n🔬 KOİN BAZLI FİLTRE ETKİ ANALİZİ")
    print("=" * 60)
    
    # Kural: Trend!=Bear/Bear AND Val!=Squeeze AND V-Mom > 1.0
    mask = (
        (df['trend_score'] != "Bear/Bear") & 
        (df['val_type'] != "Squeeze") &
        (df['vmom'] > 1.0)
    )
    
    df['kept'] = mask
    
    # Group By Symbol
    # Calculate: Total Signals, Kept Signals, Lost Diamonds
    results = []
    
    symbols = df['symbol'].unique()
    
    total_coins = len(symbols)
    diamond_killers = [] # Coins that lost diamonds
    wiped_out = [] # Coins that lost ALL signals
    improved = [] # Coins where success rate went UP
    
    print(f"Toplam İncelenen Koin: {total_coins}")
    
    for sym in symbols:
        sub = df[df['symbol'] == sym]
        total = len(sub)
        kept_sub = sub[sub['kept']]
        kept_count = len(kept_sub)
        
        # Diamond Loss
        diamonds_total = sub['is_diamond'].sum()
        diamonds_kept = kept_sub['is_diamond'].sum()
        lost_diamonds = diamonds_total - diamonds_kept
        
        # Success Rate Change
        if total > 0: pre_rate = sub['success'].mean() * 100
        else: pre_rate = 0
        
        if kept_count > 0: post_rate = kept_sub['success'].mean() * 100
        else: post_rate = 0 # Undefined actually, but let's say 0 for stats
        
        rate_diff = post_rate - pre_rate
        
        results.append({
            "symbol": sym,
            "total": total,
            "kept": kept_count,
            "diamond_loss": lost_diamonds,
            "pre_rate": pre_rate,
            "post_rate": post_rate,
            "diff": rate_diff
        })
        
        if lost_diamonds > 0:
            diamond_killers.append((sym, lost_diamonds, diamonds_total))
            
        if kept_count == 0 and total > 0:
            wiped_out.append(sym)
            
        if rate_diff > 0 and kept_count > 0:
            improved.append(sym)
            
    # Report
    print(f"\n💎 ELMAS KATLİAMI RAPORU (Diamond Kaybeden Koinler):")
    if diamond_killers:
        print(f"  Toplam {len(diamond_killers)} koinde Elmas kaybı yaşandı.")
        for item in diamond_killers:
            print(f"  - {item[0]}: {item[1]} Elmas Kaybetti (Toplamı: {item[2]} idi)")
    else:
        print("  ✅ Hiçbir koinde Elmas kaybı olmadı!")
        
    print(f"\n💀 YOK OLANLAR (Tüm Sinyalleri Silinenler):")
    print(f"  Toplam {len(wiped_out)} koin tamamen filtrelendi.")
    # Print first 10
    print(f"  Örnekler: {wiped_out[:10]}")
    
    print(f"\n🚀 İYİLEŞENLER (Başarı Oranı Artanlar):")
    print(f"  Toplam {len(improved)} koinin performansı arttı.")
    
    # Save detailed breakdown?
    # Maybe not needed, just the insights.

if __name__ == "__main__":
    df = parse_report()
    if not df.empty:
        analyze_filter_impact_per_coin(df)
    else:
        print("HATA: Veri okunamadı!")
