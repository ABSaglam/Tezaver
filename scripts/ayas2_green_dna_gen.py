#!/usr/bin/env python3
"""
YESİL LISTE: DNA MÜJDE JENERATÖRÜ
=================================
Hedef: Temizlenmiş Yeşil Liste (v17) için en iyi kuralları bulmak.
Girdi: refined_global_report_green_CLEANED.md
Çıktı: data/dna_mujde_rules_green.json
"""

import re
import pandas as pd
import numpy as np
import json
import os

REPORT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_green_CLEANED.md"
RULES_FILE = "/Users/alisaglam/TezaverMac/data/dna_mujde_rules_green.json"
AUDIT_REPORT = "/Users/alisaglam/TezaverMac/dna_mujde_audit_report_green.md"

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
            # SYM
            sym = parts[2].strip()
            
            # TIER
            tier_raw = parts[14].strip()
            if "💎" in tier_raw: tier_label = "Diamond"
            elif "🥇" in tier_raw: tier_label = "Gold"
            elif "🥈" in tier_raw: tier_label = "Silver"
            elif "🥉" in tier_raw: tier_label = "Bronze"
            else: tier_label = "NoTier"
            
            is_success = tier_label != "NoTier"
            is_diamond = tier_label == "Diamond"
            is_gold = tier_label == "Gold"
            
            # TREND (4H | 1H)
            trend_raw = parts[8].strip() # V17 format usually similar
            if trend_raw.count("🟢") == 2: trend_score = "Bull/Bull"
            elif trend_raw.count("🔴") == 2: trend_score = "Bear/Bear"
            else: trend_score = "Mixed"

            # POS/VAL/ADX parsing - verify V17 columns
            # Assuming V17 structure matches recent files (based on previous cat)
            # V17: NO|SYM|...|TREND|POS|...|VAL|...|ADX|...|V-Mom|
            
            val_raw = parts[12] # Check V17 column map
            if "💚" in val_raw: val_type = "Squeeze" 
            elif "❤️" in val_raw: val_type = "Danger"
            else: val_type = "Normal"
            
            # V-Mom (Col 26 usually)
            vmom_clean = 0
            if len(parts) > 26:
                vmom_raw = parts[26]
                vmom_clean = float(re.sub(r"[^0-9.]", "", vmom_raw)) if re.sub(r"[^0-9.]", "", vmom_raw) else 0.0
            
            # ADX (Col 20)
            adx_clean = 0
            if len(parts) > 20:
                adx_raw = parts[20]
                adx_clean = float(re.sub(r"[^0-9.]", "", adx_raw)) if re.sub(r"[^0-9.]", "", adx_raw) else 0

            data.append({
                "symbol": sym,
                "tier": tier_label,
                "success": is_success,
                "is_diamond": is_diamond,
                "is_gold": is_gold,
                "trend_score": trend_score,
                "val_type": val_type,
                "vmom": vmom_clean,
                "adx": adx_clean
            })
            
        except Exception as e:
            continue

    return pd.DataFrame(data)

def apply_strategy(df, strat_name):
    # Same strategies as Yellow List
    if strat_name == "Base": return df
    elif strat_name == "S1_NoBear": return df[df['trend_score'] != "Bear/Bear"]
    elif strat_name == "S2_Vol": return df[df['vmom'] > 1.0]
    elif strat_name == "S3_NoSqueeze": return df[df['val_type'] != "Squeeze"]
    elif strat_name == "S4_Müjde": return df[(df['trend_score'] != "Bear/Bear") & (df['val_type'] != "Squeeze") & (df['vmom'] > 1.0)]
    elif strat_name == "S5_NoBear_Vol": return df[(df['trend_score'] != "Bear/Bear") & (df['vmom'] > 1.0)]
    elif strat_name == "S7_Strict_ADX": return df[df['adx'] > 20]
    return df

def generate_rules(df):
    symbols = df['symbol'].unique()
    print(f"Toplam {len(symbols)} koin analiz ediliyor...")
    
    rules_map = {}
    audit_lines = ["# DNA MÜJDE (YEŞİL) AUDITRAPORU", f"Tarih: {pd.Timestamp.now()}", f"Koin: {len(symbols)}\n"]
    audit_lines.append("| Coin | Selected Strategy | Win Rate (Pre -> Post) | Signals (Pre -> Post) | Diamond Loss |")
    audit_lines.append("|---|---|---|---|---|")
    
    strategies = ["Base", "S1_NoBear", "S2_Vol", "S3_NoSqueeze", "S4_Müjde", "S5_NoBear_Vol", "S7_Strict_ADX"]
    
    for sym in symbols:
        sub = df[df['symbol'] == sym]
        if len(sub) == 0: continue
        
        base_diamonds = sub['is_diamond'].sum()
        base_golds = sub['is_gold'].sum()
        base_total = len(sub)
        base_wins = sub['success'].sum()
        base_wr = (base_wins / base_total) * 100 if base_total > 0 else 0
        
        best_strat = "Base"
        best_score = -9999
        best_stats = {}
        
        for strat in strategies:
            filtered = apply_strategy(sub, strat)
            f_total = len(filtered)
            
            if f_total == 0: 
                score = 0 if base_wr == 0 else -9999
            else:
                f_wins = filtered['success'].sum()
                f_diamonds = filtered['is_diamond'].sum()
                f_golds = filtered['is_gold'].sum()
                f_wr = (f_wins / f_total) * 100
                
                # Scoring (Prioritize Diamonds)
                d_loss = base_diamonds - f_diamonds
                g_loss = base_golds - f_golds
                penalty = (d_loss * 500) + (g_loss * 50)
                
                score = (f_wr - base_wr) - penalty
            
            if score > best_score:
                best_score = score
                best_strat = strat
                best_stats = {"wr": (filtered['success'].sum()/f_total)*100 if f_total>0 else 0, "total": f_total, "d_loss": base_diamonds - (filtered['is_diamond'].sum() if f_total > 0 else 0)}

        # Map to JSON format
        rule_def = {
            "strategy": best_strat,
            "trend_filter": best_strat in ["S1_NoBear", "S4_Müjde", "S5_NoBear_Vol"],
            "val_filter": best_strat in ["S3_NoSqueeze", "S4_Müjde"],
            "vol_filter": best_strat in ["S2_Vol", "S4_Müjde", "S5_NoBear_Vol"],
            "adx_filter": best_strat == "S7_Strict_ADX",
            "pos_filter": False
        }
        rules_map[sym] = rule_def
        
        audit_lines.append(f"| {sym} | {best_strat} | {base_wr:.1f}% -> {best_stats.get('wr', base_wr):.1f}% | {base_total} -> {best_stats.get('total', base_total)} | {best_stats.get('d_loss', 0)} |")

    with open(RULES_FILE, "w") as f:
        json.dump(rules_map, f, indent=4)
        
    with open(AUDIT_REPORT, "w") as f:
        f.write("\n".join(audit_lines))
        
    print(f"✅ Kurallar: {RULES_FILE}")
    print(f"✅ Rapor: {AUDIT_REPORT}")

if __name__ == "__main__":
    df = parse_report()
    if not df.empty:
        generate_rules(df)
    else:
        print("Veri yok.")
