import json
import pandas as pd
from datetime import datetime

INPUT_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys.json"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/FAZ100_GLOBAL_REPORT.md"

def generate_report():
    print(f"Loading {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    report_lines = []
    report_lines.append("# 🦅 FAZ-100 GLOBAL RAPORU (TÜM KOİNLER)")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append(f"Total Coins with Phase-100 DNA: {len(data)}")
    report_lines.append("") 
    report_lines.append("| Coin | 🦅 Sinyal | WR% | 💎 Diamond | 🥇 Gold | 🥈 Silver | 🥉 Bronze | 🔴 Kayıp |")
    report_lines.append("|---|---|---|---|---|---|---|---|")

    # Aggregating Stats per Coin
    rows = []
    
    for symbol, keys in data.items():
        total_signals = 0
        total_wins = 0
        t_diamond = 0
        t_gold = 0
        t_silver = 0
        t_bronze = 0
        t_loss = 0
        
        for dna, stats in keys.items():
            # count stats
            s_diamond = stats.get('DIAMOND', 0)
            s_gold = stats.get('GOLD', 0)
            s_silver = stats.get('SILVER', 0)
            s_bronze = stats.get('BRONZE', 0)
            s_notier = stats.get('NOTIER', 0)
            s_total = stats.get('TOTAL', 0)
            
            # Using standard success metric (Notier is fail)
            s_success = s_diamond + s_gold + s_silver + s_bronze
            
            total_signals += s_total
            total_wins += s_success
            t_diamond += s_diamond
            t_gold += s_gold
            t_silver += s_silver
            t_bronze += s_bronze
            t_loss += s_notier
            
        wr = (total_wins / total_signals * 100) if total_signals > 0 else 0
        
        rows.append({
            'symbol': symbol,
            'sig': total_signals,
            'wr': wr,
            'diamond': t_diamond,
            'gold': t_gold,
            'silver': t_silver,
            'bronze': t_bronze,
            'loss': t_loss
        })

    # Sort by Symbol Alphabetical
    rows.sort(key=lambda x: x['symbol'])
    
    for r in rows:
        # Highlight Diamond heavy coins
        diamond_icon = "💎" if r['diamond'] > 0 else "-"
        
        line = f"| **{r['symbol']}** | {r['sig']} | %{r['wr']:.1f} | {diamond_icon}{r['diamond']} | {r['gold']} | {r['silver']} | {r['bronze']} | 🔴{r['loss']} |"
        report_lines.append(line)

    with open(OUTPUT_FILE, 'w') as f:
        f.write("\n".join(report_lines))
        
    print(f"✅ Report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()
