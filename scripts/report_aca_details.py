import json
import pandas as pd
from tezaver.core.rally_store import RallyStore

def report_aca_v4_details():
    symbol = "ACAUSDT"
    print(f"📄 GENERATING DETAILED v4 REPORT FOR {symbol}")
    
    with open(f"data/final_v4_{symbol}.json", "r") as f:
        final_v4 = json.load(f)
        
    allowed_families = set(final_v4.get('allowed_families', []))
    with open(f"data/profiles_{symbol}.json", "r") as f:
        all_profiles = json.load(f)
        
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    
    # Map normalized date -> rally info
    rally_map = {}
    for r in all_rallies:
        if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']:
            d = pd.Timestamp(r['event_time']).normalize()
            rally_map[d] = {
                'tier': r.get('tier'),
                'gain': r.get('gain', 0) or r.get('pnl', 0) # Fallback if gain is missing
            }
            
    signals = []
    
    for d_str, p in all_profiles.items():
        key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
        
        if key in allowed_families:
            signal_date = pd.Timestamp(d_str)
            target_date = signal_date + pd.Timedelta(days=1)
            
            if target_date in rally_map:
                r_info = rally_map[target_date]
                signals.append({
                    'signal_date': d_str,
                    'rally_date': target_date.strftime('%Y-%m-%d'),
                    'tier': r_info['tier'],
                    'gain': r_info['gain']
                })

    # Sort by Date
    signals.sort(key=lambda x: x['signal_date'])
    
    # Generate Markdown
    md = f"# 🚇 ACAUSDT v4 (SAF TAHMİN) DETAYLI DÖKÜM\n\n"
    md += f"**Toplam Sinyal:** {len(signals)}\n"
    md += f"**Kural:** Sinyal Günü (T=0) -> Ralli Ertesi Gün (T+1)\n\n"
    
    md += "| Sinyal Tarihi | Beklenen Ralli (T+1) | Tier | Kazanç (%) |\n"
    md += "| :--- | :--- | :--- | :--- |\n"
    
    for s in signals:
        icon = "💎" if s['tier'] == 'DIAMOND' else "🥇" if s['tier'] == 'GOLD' else "🥈"
        gain_str = f"%{s['gain']:.2f}" if s['gain'] else "N/A"
        md += f"| {s['signal_date']} | {s['rally_date']} | {icon} {s['tier']} | {gain_str} |\n"
        
    md += "\n> **Not:** Bu liste sadece T+1 gününde kesin ralli getiren 'Saf' sinyallerdir.\n"
    
    out_path = f"/Users/alisaglam/.gemini/antigravity/brain/74eb5317-8de8-4465-8305-2b29d5903605/aca_v4_detailed_list.md"
    with open(out_path, "w") as f:
        f.write(md)
        
    print(f"✅ Detailed report saved: {out_path}")

if __name__ == "__main__":
    report_aca_v4_details()
