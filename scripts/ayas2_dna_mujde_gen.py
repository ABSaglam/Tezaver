#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2: DNA MÜJDE JENERATÖRÜ (KOİN BAZLI KURALLAR)
=========================================================
Hedef: Her koin için en optimize filtre kuralını bulmak.
"Tembellik Yok": Her koin için 8 farklı strateji denenir.

Girdi: refined_global_report_list2_CLEANED.md
Çıktı 1: data/dna_mujde_rules.json (Scanner için)
Çıktı 2: dna_mujde_audit_report.md (Kullanıcı için detaylı rapor)
"""

import re
import pandas as pd
import numpy as np
import json
import os

REPORT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_list2_CLEANED.md"
RULES_FILE = "/Users/alisaglam/TezaverMac/data/dna_mujde_rules.json"
AUDIT_REPORT = "/Users/alisaglam/TezaverMac/dna_mujde_audit_report.md"

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
            trend_raw = parts[8].strip()
            if trend_raw.count("🟢") == 2: trend_score = "Bull/Bull"
            elif trend_raw.count("🔴") == 2: trend_score = "Bear/Bear"
            else: trend_score = "Mixed"

            # POS
            pos_raw = parts[9].strip()
            if "🟢" in pos_raw: pos_val = "Bullish"
            elif "🔴" in pos_raw: pos_val = "Bearish"
            else: pos_val = "Neutral"

            # VAL
            val_raw = parts[12].strip()
            if "💚" in val_raw: val_type = "Squeeze" 
            elif "❤️" in val_raw: val_type = "Danger"
            else: val_type = "Normal"
            
            # V-Mom
            vmom_raw = parts[26]
            vmom_clean = vmom_raw.lower().replace("x", "").strip()
            vmom = float(vmom_clean) if vmom_clean else 0.0
            
            # ADX
            adx_raw = parts[20]
            adx_clean = re.sub(r"[^0-9.]", "", adx_raw)
            adx = float(adx_clean) if adx_clean else 0

            data.append({
                "symbol": sym,
                "tier": tier_label,
                "success": is_success,
                "is_diamond": is_diamond,
                "is_gold": is_gold,
                "trend_score": trend_score,
                "pos_val": pos_val,
                "val_type": val_type,
                "vmom": vmom,
                "adx": adx
            })
            
        except Exception:
            continue

    return pd.DataFrame(data)

def apply_strategy(df, strat_name):
    if strat_name == "Base":
        return df
    elif strat_name == "S1_NoBear":
        return df[df['trend_score'] != "Bear/Bear"]
    elif strat_name == "S2_Vol":
        return df[df['vmom'] > 1.0]
    elif strat_name == "S3_NoSqueeze":
        return df[df['val_type'] != "Squeeze"]
    elif strat_name == "S4_Müjde": # Combined
        return df[
            (df['trend_score'] != "Bear/Bear") & 
            (df['val_type'] != "Squeeze") &
            (df['vmom'] > 1.0)
        ]
    elif strat_name == "S5_NoBear_Vol":
        return df[
            (df['trend_score'] != "Bear/Bear") & 
            (df['vmom'] > 1.0)
        ]
    elif strat_name == "S6_Context": # Avoid Bullish POS (Top Selling) based on previous analysis
        return df[df['pos_val'] != "Bullish"]
    elif strat_name == "S7_Strict_ADX":
        return df[df['adx'] > 20]
    return df

def generate_rules(df):
    symbols = df['symbol'].unique()
    print(f"Toplam {len(symbols)} koin analiz ediliyor...")
    
    rules_map = {}
    audit_lines = []
    audit_lines.append("# DNA MÜJDE AUDIT RAPORU")
    audit_lines.append(f"Tarih: {pd.Timestamp.now()}")
    audit_lines.append(f"Taranan Koin Sayısı: {len(symbols)}\n")
    audit_lines.append("| Coin | Selected Strategy | Win Rate (Pre -> Post) | Signals (Pre -> Post) | Diamond Loss | Reason |")
    audit_lines.append("|---|---|---|---|---|---|")
    
    strategies = ["Base", "S1_NoBear", "S2_Vol", "S3_NoSqueeze", "S4_Müjde", "S5_NoBear_Vol", "S6_Context", "S7_Strict_ADX"]
    
    stats_counter = {"Improved": 0, "Same": 0, "Worsened": 0} # Though we aim to improve
    
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
            
            if f_total == 0: # Avoid killing the coin completely unless it was 0% win rate
                if base_wr == 0: 
                    # If it was garbage, killing it is fine, but maybe keep Base to show it's garbage?
                    # Or select strategy that kills it.
                    score = 0
                else:
                    score = -9999 # Don't select a strategy that kills a potentially good coin
            else:
                f_wins = filtered['success'].sum()
                f_diamonds = filtered['is_diamond'].sum()
                f_golds = filtered['is_gold'].sum()
                f_wr = (f_wins / f_total) * 100
                
                # SCORING ALGORITHM
                # 1. Diamond Protection (Critical)
                diamond_loss = base_diamonds - f_diamonds
                # If we lose diamonds, huge penalty unless base WR was terrible (<20%)
                
                penalty = 0
                if diamond_loss > 0:
                    penalty += 500 * diamond_loss # Very strict on diamonds
                
                # 2. Gold Protection
                gold_loss = base_golds - f_golds
                if gold_loss > 0:
                    penalty += 50 * gold_loss
                    
                # 3. Win Rate Bonus
                wr_gain = f_wr - base_wr
                
                # 4. Signal Retention
                # We don't want to filter too much if WR gain is minimal.
                # But if WR gain is huge, we accept signal loss.
                
                score = wr_gain - penalty
                
            if score > best_score:
                best_score = score
                best_strat = strat
                best_stats = {
                    "wr": f_wr if f_total > 0 else 0,
                    "total": f_total,
                    "diamonds": f_diamonds if f_total > 0 else 0,
                    "diamond_loss": base_diamonds - (filtered['is_diamond'].sum() if f_total > 0 else 0)
                }
        
        # Determine Logic String for JSON
        # Map Strategy Name to Flags
        # Flags: trend_filter, val_filter, vol_filter, pos_filter, adx_filter
        
        rule_def = {
            "strategy": best_strat,
            "trend_filter": False,
            "val_filter": False,
            "vol_filter": False,
            "pos_filter": False,
            "adx_filter": False
        }
        
        if best_strat == "S1_NoBear": rule_def["trend_filter"] = True
        elif best_strat == "S2_Vol": rule_def["vol_filter"] = True
        elif best_strat == "S3_NoSqueeze": rule_def["val_filter"] = True
        elif best_strat == "S4_Müjde": 
            rule_def["trend_filter"] = True
            rule_def["val_filter"] = True
            rule_def["vol_filter"] = True
        elif best_strat == "S5_NoBear_Vol":
            rule_def["trend_filter"] = True
            rule_def["vol_filter"] = True
        elif best_strat == "S6_Context": rule_def["pos_filter"] = True
        elif best_strat == "S7_Strict_ADX": rule_def["adx_filter"] = True
        
        rules_map[sym] = rule_def
        
        # Logging
        row_str = f"| {sym} | {best_strat} | {base_wr:.1f}% -> {best_stats.get('wr', base_wr):.1f}% | {base_total} -> {best_stats.get('total', base_total)} | {best_stats.get('diamond_loss', 0)} | Score: {best_score:.1f} |"
        audit_lines.append(row_str)
        
    # Save Rules
    with open(RULES_FILE, "w") as f:
        json.dump(rules_map, f, indent=4)
        print(f"✅ Kurallar kaydedildi: {RULES_FILE}")
        
    # Save Report
    with open(AUDIT_REPORT, "w") as f:
        f.write("\n".join(audit_lines))
    print(f"✅ Audit Raporu kaydedildi: {AUDIT_REPORT}")

if __name__ == "__main__":
    df = parse_report()
    if not df.empty:
        generate_rules(df)
    else:
        print("HATA: Veri okunamadı!")
