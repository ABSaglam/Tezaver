#!/usr/bin/env python3
"""
📊 ASM v8 DETAILED AUDIT REPORT

26 rallinin her birini tek tek inceler:
- Nerede, neden girdi? (Trend vs Reversion)
- Nerede, neden çıktı? (Hangi Stage/Reason)
- ASM PnL vs Ralli % (Verimlilik)
"""

import json
import pandas as pd
from asm_v8_harmony import HarmonyASM_v8

def run_detailed_audit():
    # Load Data
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1.sort_index(inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    print("🧐 ALGO ASM v8 - 26 RALLY DEEP AUDIT")
    print("="*105)
    print(f"{'DATE':12} | {'TIER':8} | {'RALLY%':7} | {'ENTRY':25} | {'EXIT':25} | {'ASM%':7} | {'EFF%':5}")
    print("-"*105)
    
    audit_results = []
    
    for rally in rally_data:
        asm = HarmonyASM_v8(rally, df_h1)
        
        # We need to peek inside the entry logic to see WHY it entered
        # Let's override/re-calculate entry reason for the report
        soul_pass, min_comp = asm.check_h1_soul_pass()
        
        res = asm.run()
        
        entry_desc = "SKIPPED: " + res.get('reason', 'N/A')
        exit_desc = res.get('reason', 'N/A')
        pnl = res.get('pnl', 0)
        rally_pct = rally.get('rally_pct', 0)
        efficiency = (pnl / rally_pct * 100) if rally_pct > 0 and pnl > 0 else 0
        
        if res.get('entry_idx') is not None:
            # Re-determine entry trigger for reporting
            c = rally['15m_data'][res['entry_idx']]
            if (c.get('vol_ratio', 0) > 2.0 and c.get('rsi', 100) < 30):
                entry_desc = f"REVERSION (C{res['entry_idx']})"
            else:
                entry_desc = f"TREND (C{res['entry_idx']})"
            
            exit_desc = f"{res['reason']} (C{res['exit_idx']})"
        
        row = {
            'date': rally['date'],
            'tier': rally['tier'],
            'rally_pct': rally_pct,
            'entry': entry_desc,
            'exit': exit_desc,
            'pnl': pnl,
            'efficiency': efficiency
        }
        audit_results.append(row)
        
        print(f"{row['date']:12} | {row['tier']:8} | {row['rally_pct']:6.1f}% | {row['entry']:25} | {row['exit']:25} | {row['pnl']:+6.2f}% | {row['efficiency']:4.0f}%")

    # Grouped Summary
    print("-"*105)
    df = pd.DataFrame(audit_results)
    trades = df[df['pnl'] != 0] # Non-skipped
    
    print(f"\n📈 TOTAL PNL: {df['pnl'].sum():+.2f}%")
    print(f"📊 AVG EFFICIENCY: {trades['efficiency'].mean():.1f}% (per successful trade)")
    print(f"✅ RALLIES CAUGHT: {len(trades)}/26")
    
    # Save detailed JSON
    with open("data/asm_v8_detailed_audit.json", "w") as f:
        json.dump(audit_results, f, indent=2)

if __name__ == "__main__":
    run_detailed_audit()
