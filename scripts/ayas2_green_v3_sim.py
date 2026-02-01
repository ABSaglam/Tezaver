#!/usr/bin/env python3
"""
YESİL LİSTE V3: DNA MÜJDE SİMÜLASYONU
=====================================
Hedef: %92.4 Başarılı V3 Baseline listesini daha da iyileştirebilir miyiz?
Girdi: YESIL_LISTE_V3_BASELINE.md
Çıktı: dna_mujde_audit_report_green_v3.md
"""

import re
import pandas as pd
import numpy as np
import json
import os

REPORT_FILE = "/Users/alisaglam/TezaverMac/YESIL_LISTE_V3_BASELINE.md"
RULES_FILE = "/Users/alisaglam/TezaverMac/data/dna_mujde_rules_green_v3.json"
AUDIT_REPORT = "/Users/alisaglam/TezaverMac/dna_mujde_audit_report_green_v3.md"

def parse_report():
    print(f"Rapor okunuyor: {REPORT_FILE}")
    with open(REPORT_FILE, "r") as f:
        lines = f.readlines()
        
    data = []
    
    for line in lines:
        if not line.strip().startswith("|"): continue
        if "---" in line or "NO" in line and "SYM" in line: continue
        
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 20: continue 

        try:
            sym = parts[2].strip()
            tier_raw = parts[14].strip()
            if "💎" in tier_raw: tier = "Diamond"
            elif "🥇" in tier_raw: tier = "Gold"
            elif "🥈" in tier_raw: tier = "Silver"
            elif "🥉" in tier_raw: tier = "Bronze"
            else: tier = "NoTier"
            
            is_success = tier != "NoTier"
            
            # Trend Score & Vol parsing
            # V3 Baseline format writes trend emoji but stores "Bear" internally in logic? 
            # Actually Baseline report printed "🟡" for all trends (Trend emoji line 245 in scanner).
            # WAIT. The scanner code printed "🟡" hardcoded!
            # We CANNOT simulate trend filters if the report doesn't contain the trend data.
            # 
            # Re-checking scanner code...
            # Line 245: trend_emoji = "🟡" 
            # Line 247: ... | {trend_emoji} | ...
            # 
            # BIG ISSUE: Use cannot simulate "NoBear" strategies because we didn't save the Trend status in the report!
            # 
            # HOWEVER, we have 'v_mom_val' and 'adx_val' in the report columns (last columns).
            # Column 26: V-Mom. Column 20: ADX.
            
            # ADX
            adx_val = 0
            if len(parts) > 20:
                adx_raw = parts[20]
                adx_val = float(re.sub(r"[^0-9.]", "", adx_raw)) if re.sub(r"[^0-9.]", "", adx_raw) else 0

            # V-Mom
            vmom_val = 0
            if len(parts) > 26:
                vmom_raw = parts[26]
                vmom_val = float(re.sub(r"[^0-9.]", "", vmom_raw)) if re.sub(r"[^0-9.]", "", vmom_raw) else 0

            data.append({
                "symbol": sym,
                "tier": tier,
                "success": is_success,
                "is_diamond": tier == "Diamond",
                "is_gold": tier == "Gold",
                "trend_sim": "Neutral", # Trend data lost in baseline print
                "vmom": vmom_val,
                "adx": adx_val
            })
            
        except Exception as e: continue

    return pd.DataFrame(data)

def apply_strategy(df, strat_name):
    # Valid Strategies (Only Vol/ADX possible due to missing Trend data)
    if strat_name == "Base": return df
    elif strat_name == "S2_Vol": return df[df['vmom'] > 1.0]
    elif strat_name == "S7_Strict_ADX": return df[df['adx'] > 20]
    elif strat_name == "S8_Vol_ADX": return df[(df['vmom'] > 1.0) & (df['adx'] > 20)]
    return df

def generate_simulation(df):
    symbols = df['symbol'].unique()
    print(f"Toplam {len(symbols)} koin simüle ediliyor...")
    
    audit_lines = ["# DNA MÜJDE V3 SİMÜLASYONU (Trend Verisi Yok - Sadece Vol/ADX)", f"Tarih: {pd.Timestamp.now()}", "Strategy: Base vs Vol vs ADX\n"]
    audit_lines.append("| Coin | WINNER Strat | WR (Base -> New) | Signals (Base -> New) | Diamonds Saved |")
    audit_lines.append("|---|---|---|---|---|")
    
    strategies = ["Base", "S2_Vol", "S7_Strict_ADX", "S8_Vol_ADX"]
    
    global_base_wins = 0
    global_new_wins = 0
    global_base_total = 0
    global_new_total = 0
    
    total_strategies = {"Base":0, "S2_Vol":0, "S7_Strict_ADX":0, "S8_Vol_ADX":0}
    rules_map = {}

    for sym in symbols:
        sub = df[df['symbol'] == sym]
        if len(sub) == 0: continue
        
        base_wr = (sub['success'].sum() / len(sub)) * 100
        base_diamonds = sub['is_diamond'].sum()
        
        best_strat = "Base"
        best_score = -9999
        best_stats = {}
        
        for strat in strategies:
            filtered = apply_strategy(sub, strat)
            f_total = len(filtered)
            if f_total == 0:
                score = -9999
            else:
                f_wins = filtered['success'].sum()
                f_wr = (f_wins / f_total) * 100
                f_diamonds = filtered['is_diamond'].sum()
                
                # Scoring: Maximize WR, but heavily penalize Diamond Loss
                d_loss = base_diamonds - f_diamonds
                score = (f_wr - base_wr) - (d_loss * 500) 
                
                # Signal Preservation Bonus (if WR is equal/similar, prefer more signals)
                if abs(f_wr - base_wr) < 1:
                    if f_total > len(sub) * 0.8: score += 10
            
            if score > best_score:
                best_score = score
                best_strat = strat
                best_stats = {
                    "wr": (filtered['success'].sum() / f_total)*100 if f_total>0 else 0,
                    "total": f_total,
                    "d_loss": base_diamonds - (filtered['is_diamond'].sum() if f_total>0 else 0),
                    "wins": filtered['success'].sum()
                }
        
        total_strategies[best_strat] += 1
        global_base_total += len(sub)
        global_base_wins += sub['success'].sum()
        
        if best_strat == "Base":
            global_new_total += len(sub)
            global_new_wins += sub['success'].sum()
        else:
             global_new_total += best_stats['total']
             global_new_wins += best_stats['wins']

        # Save Rule (Compatible with Scanner)
        rules_map[sym] = {
            "strategy": best_strat,
            "trend_filter": False, # Trend data missing in Baseline, so never enable trend filter here
            "val_filter": False,
            "vol_filter": best_strat in ["S2_Vol", "S8_Vol_ADX"],
            "adx_filter": best_strat in ["S7_Strict_ADX", "S8_Vol_ADX"],
            "pos_filter": False
        }

        audit_lines.append(f"| {sym} | {best_strat} | {base_wr:.0f}% -> {best_stats.get('wr', base_wr):.0f}% | {len(sub)} -> {best_stats.get('total', len(sub))} | {best_stats.get('d_loss', 0)} Loss |")

    with open(RULES_FILE, "w") as f:
        json.dump(rules_map, f, indent=4)
        
    with open(AUDIT_REPORT, "w") as f:
        f.write("\n".join(audit_lines))
        
    print(f"✅ Kurallar Kaydedildi: {RULES_FILE}")
        
    print(f"✅ Simülasyon Tamamlandı: {AUDIT_REPORT}")
    
    final_base_wr = (global_base_wins / global_base_total) * 100
    final_new_wr = (global_new_wins / global_new_total) * 100
    
    print("\nGENEL SONUÇLAR:")
    print(f"Base (Filtresiz) Başarı: %{final_base_wr:.2f} ({global_base_total} Sinyal)")
    print(f"Müjde (Optimize) Başarı: %{final_new_wr:.2f} ({global_new_total} Sinyal)")
    print(f"Fark: +%{final_new_wr - final_base_wr:.2f}")
    print("\nStrateji Dağılımı:")
    print(total_strategies)

if __name__ == "__main__":
    df = parse_report()
    if not df.empty:
        generate_simulation(df)
