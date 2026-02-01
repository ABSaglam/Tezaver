#!/usr/bin/env python3
import pandas as pd

FILE_OLD = "/Users/alisaglam/TezaverMac/refined_global_report_list2_only.md"
FILE_NEW = "/Users/alisaglam/TezaverMac/refined_global_report_final_mujde.md"

def get_stats(path):
    try:
        with open(path, "r") as f:
            lines = f.readlines()
            
        tiers = {"Diamond": 0, "Gold": 0, "Silver": 0, "Bronze": 0, "NoTier": 0}
        total = 0
        
        for line in lines:
            if not line.strip().startswith("|") or "---" in line or "NO" in line: continue
            
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 15: continue
            
            tier_raw = parts[14]
            if "💎" in tier_raw: tiers["Diamond"] += 1
            elif "🥇" in tier_raw: tiers["Gold"] += 1
            elif "🥈" in tier_raw: tiers["Silver"] += 1
            elif "🥉" in tier_raw: tiers["Bronze"] += 1
            else: tiers["NoTier"] += 1
            total += 1
            
        success = tiers["Diamond"] + tiers["Gold"] + tiers["Silver"] + tiers["Bronze"]
        rate = (success / total) * 100 if total > 0 else 0
        return tiers, total, rate, success
    except:
        return {}, 0, 0, 0

def compare():
    t_old, tot_old, rate_old, succ_old = get_stats(FILE_OLD)
    t_new, tot_new, rate_new, succ_new = get_stats(FILE_NEW)
    
    print("\n⚔️ KARŞILAŞTIRMALI RAPOR: ÖNCE vs SONRA")
    print("=" * 60)
    
    print(f"📄 ESKİ (Ham Liste): {tot_old} Sinyal | Başarı: %{rate_old:.1f}")
    print(f"📄 YENİ (Müjde):     {tot_new} Sinyal | Başarı: %{rate_new:.1f}")
    print(f"🚀 İyileşme:         +%{rate_new - rate_old:.1f} Puan")
    print("-" * 60)
    
    headers = ["Tier", "Icon", "Eski", "Yeni", "Fark (Kayıp/Kazanç)"]
    row_fmt = "{:<10} {:<4} {:<8} {:<8} {:<20}"
    print(row_fmt.format(*headers))
    print("-" * 60)
    
    tier_map = [
        ("Diamond", "💎"),
        ("Gold", "🥇"),
        ("Silver", "🥈"),
        ("Bronze", "🥉"),
        ("NoTier", "❌")
    ]
    
    for name, icon in tier_map:
        old_val = t_old.get(name, 0)
        new_val = t_new.get(name, 0)
        diff = new_val - old_val
        diff_str = f"{diff} (Kayıp)" if diff < 0 else f"{diff}"
        if name == "NoTier" and diff < 0: diff_str = f"{diff} (Temizlendi!)"
        
        print(row_fmt.format(name, icon, old_val, new_val, diff_str))
        
    print("-" * 60)
    print("YORUM:")
    
    # Diamond Check
    d_diff = t_new.get("Diamond", 0) - t_old.get("Diamond", 0)
    if d_diff == 0:
        print("✅ MÜKEMMEL: Hiç Elmas kaybetmedik!")
    elif d_diff < 0:
        print(f"⚠️ UYARI: {abs(d_diff)} Elmas kaybettik. (Kabul edilebilir mi?)")
        
    # NoTier Check
    trash_diff = t_new.get("NoTier", 0) - t_old.get("NoTier", 0)
    print(f"✅ TEMİZLİK: {abs(trash_diff)} adet çöp sinyal atıldı.")

if __name__ == "__main__":
    compare()
