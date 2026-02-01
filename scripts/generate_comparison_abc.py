import pandas as pd
import re
import os

# Load Pure DNA Reports (A, B, C)
pure_files = ["PURE_DNA_REPORT_A.md", "PURE_DNA_REPORT_B.md", "PURE_DNA_REPORT_C.md"]
pure_data = {}

for fpath in pure_files:
    if not os.path.exists(fpath): continue
    with open(fpath, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if "|" not in line or "Total Sinyal" in line or "---" in line: continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8: continue
            
            # Extract Coin Name (**COIN**)
            coin = parts[1].replace("*", "").replace(" ", "")
            total_signal = parts[2]
            golden_dna = parts[4].replace("*", "")
            diamond_count = parts[5].replace("💎", "")
            top_wr = parts[7]
            
            pure_data[coin] = {
                'pure_signal': total_signal,
                'pure_golden': golden_dna,
                'pure_diamond': diamond_count,
                'pure_wr': top_wr
            }

# Load Grand Batch Report (for Yellow/Green comparison)
grand_file = "GRAND_REPORT_BATCH_1.md"
yellow_green_data = {}

if os.path.exists(grand_file):
    with open(grand_file, 'r') as f:
        lines = f.readlines()
        current_coin = None
        for line in lines:
            if "|" not in line or "System" in line or "---" in line: continue
            parts = [p.strip() for p in line.split("|")]
            
            # Coin row
            if parts[1]: 
                current_coin = parts[1].replace("*", "").replace(" ", "")
                if current_coin not in yellow_green_data:
                    yellow_green_data[current_coin] = {'y_wr': '-', 'y_sig': '-', 'y_loss': '-', 'g_wr': '-', 'g_sig': '-', 'g_loss': '-'}
            
            # System Data
            system = parts[2].lower()
            wr = parts[4]
            sig = parts[5]
            loss = parts[6].replace("🔻", "")
            
            if "yellow" in system:
                yellow_green_data[current_coin]['y_wr'] = wr
                yellow_green_data[current_coin]['y_sig'] = sig
                yellow_green_data[current_coin]['y_loss'] = loss
            elif "green" in system:
                yellow_green_data[current_coin]['g_wr'] = wr
                yellow_green_data[current_coin]['g_sig'] = sig
                yellow_green_data[current_coin]['g_loss'] = loss

# Merge and Generate Final Report
with open("KIYASLAMA_RAPORU_ABC.md", "w") as f:
    f.write("# 🧪 DNA KIYASLAMA RAPORU (A-B-C): Saf DNA vs Filtreli (Sarı/Yeşil)\n")
    f.write("| Coin | 🧬 SAF DNA (Stratejisiz) | | | 🟡 SARI LİSTE (Filtreli) | | | 🟢 YEŞİL LİSTE (Filtreli) | | |\n")
    f.write("|---|---|---|---|---|---|---|---|---|---|\n")
    f.write("| **Sembol** | **WR** | **Sinyal** | **💎 Elmas** | **WR** | **Sinyal** | **Kayıp** | **WR** | **Sinyal** | **Kayıp** |\n")
    f.write("|---|---|---|---|---|---|---|---|---|---|\n")
    
    sorted_coins = sorted(list(pure_data.keys()))
    
    for coin in sorted_coins:
        p = pure_data[coin]
        yg = yellow_green_data.get(coin, {'y_wr': '-', 'y_sig': '-', 'y_loss': '-', 'g_wr': '-', 'g_sig': '-', 'g_loss': '-'})
        
        f.write(f"| **{coin}** | {p['pure_wr']} | {p['pure_signal']} | {p['pure_diamond']} | {yg['y_wr']} | {yg['y_sig']} | 🔻{yg['y_loss']} | {yg['g_wr']} | {yg['g_sig']} | 🔻{yg['g_loss']} |\n")

print("Report generated: KIYASLAMA_RAPORU_ABC.md")
