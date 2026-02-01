#!/usr/bin/env python3
import sys

REPORT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_v17.md"

def analyze_tiers():
    print(f"DEBUG: Analyzing {REPORT_FILE}")
    try:
        with open(REPORT_FILE, "r") as f:
            lines = f.readlines()
            
        tiers = {"Diamond": 0, "Gold": 0, "Silver": 0, "Bronze": 0, "NoTier": 0}
        total = 0
        
        for line in lines:
            if not line.strip().startswith("|") or "---" in line or "NO" in line: continue
            
            parts = [p.strip() for p in line.split("|")]
            # V17 format is same as others usually
            # Check TIER column index. Usually index 14 in V17 based on previous files.
            # Let's verify by finding the emoji.
            
            found_tier = False
            for p in parts:
                if "💎" in p: 
                    tiers["Diamond"] += 1; found_tier = True; break
                elif "🥇" in p: 
                    tiers["Gold"] += 1; found_tier = True; break
                elif "🥈" in p: 
                    tiers["Silver"] += 1; found_tier = True; break
                elif "🥉" in p: 
                    tiers["Bronze"] += 1; found_tier = True; break
            
            if not found_tier:
                # Assuming if it's a valid data row (has date/price), it counts as NoTier
                # Checking if it has date (e.g. 2024...)
                if len(parts) > 5 and "-" in parts[5]: # Time column
                     tiers["NoTier"] += 1
                elif len(parts) > 14: # Safe fallback
                     tiers["NoTier"] += 1

            total = sum(tiers.values())
            
        success = tiers["Diamond"] + tiers["Gold"] + tiers["Silver"] + tiers["Bronze"]
        rate = (success / total) * 100 if total > 0 else 0
        
        print("\n🌿 YEŞİL LİSTE (v17) ANALİZ RAPORU")
        print("=" * 60)
        print(f"📅 Rapor Tarihi: Dün (Jan 31)")
        print(f"📊 Toplam Sinyal: {total}")
        print(f"✅ Başarı Oranı:  %{rate:.1f}")
        print("-" * 60)
        
        icons = {'Diamond': '💎', 'Gold': '🥇', 'Silver': '🥈', 'Bronze': '🥉', 'NoTier': '❌'}
        
        for t in ['Diamond', 'Gold', 'Silver', 'Bronze', 'NoTier']:
            count = tiers[t]
            pct = (count / total) * 100 if total > 0 else 0
            print(f"{icons[t]} {t:<10}: {count:>5} (%{pct:.1f})")
            
        print("-" * 60)
        
        # Comparison with Yellow List (Hardcoded from previous memory for context)
        print("YORUM:")
        if rate > 80:
            print("🌟 MÜKEMMEL: Yeşil Liste zaten çok sağlam.")
        elif rate < 60:
            print("⚠️ SORUNLU: Yeşil Liste performansı düşük, filtre optimizasyonu gerekebilir.")
        else:
            print("⚖️ DENGELİ: İyi ama geliştirilebilir.")

    except Exception as e:
        print(f"HATA: {e}")

if __name__ == "__main__":
    analyze_tiers()
