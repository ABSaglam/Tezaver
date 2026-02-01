#!/usr/bin/env python3
import sys

REPORT_FILE = "/Users/alisaglam/TezaverMac/YESIL_LISTE_V3_FINAL.md"

def analyze():
    print(f"--- YEŞİL LİSTE V3 (FINAL) ANALİZİ ---")
    try:
        with open(REPORT_FILE, "r") as f:
            lines = f.readlines()
            
        tiers = {"Diamond": 0, "Gold": 0, "Silver": 0, "Bronze": 0, "NoTier": 0}
        total = 0
        
        for line in lines:
            if not line.strip().startswith("|") or "---" in line or "NO" in line: continue
            
            parts = [p.strip() for p in line.split("|")]
            found_tier = False
            for p in parts:
                if "💎" in p: tiers["Diamond"] += 1; found_tier = True; break
                elif "🥇" in p: tiers["Gold"] += 1; found_tier = True; break
                elif "🥈" in p: tiers["Silver"] += 1; found_tier = True; break
                elif "🥉" in p: tiers["Bronze"] += 1; found_tier = True; break
            
            if not found_tier: tiers["NoTier"] += 1
            total += 1
            
        success = total - tiers["NoTier"]
        rate = (success / total) * 100 if total > 0 else 0
        
        print(f"📊 Toplam Sinyal: {total}")
        print(f"✅ Başarı Oranı:  %{rate:.1f}")
        print("-" * 40)
        
        print(f"💎 Diamond: {tiers['Diamond']}")
        print(f"🥇 Gold:    {tiers['Gold']}")
        print(f"🥈 Silver:  {tiers['Silver']}")
        print(f"🥉 Bronze:  {tiers['Bronze']}")
        print(f"❌ NoTier:  {tiers['NoTier']}")
        
    except Exception as e: print(e)

if __name__ == "__main__":
    analyze()
