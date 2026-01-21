import json
import pandas as pd
import sys
import os
from tezaver.core.rally_store import RallyStore

def report_v4_details(symbol):
    print(f"📄 GENERATING DETAILED v4 REPORT FOR {symbol}")
    
    key_path = f"data/golden_keys/{symbol}_key.json"
    if not os.path.exists(key_path):
        print(f"❌ Golden Key not found for {symbol}. Run forge_golden_key.py first.")
        return

    with open(key_path, "r") as f:
        key_data = json.load(f)
        
    allowed_families = set(key_data.get('golden_dna_list', []))
    
    # Load Data (Re-profiling needed since we store keys, not all daily profiles)
    try:
        df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
        df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
        df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
    except Exception as e:
        print(f"❌ Read Error: {e}")
        return

    for df in [df_w, df_d, df_h4, df_h1]:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

    # --- Profile Logic (Must match forge_golden_key.py EXACTLY) ---
    def get_profile(day):
        sub_w = df_w[df_w.index <= day]
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        faz = "neutral"
        if rsi_val < 40: faz = "derin_dip"
        elif rsi_val < 60: faz = "birikim_fazi"
        elif rsi_val < 75: faz = "yukselis_fazi"
        else: faz = "asiri_alim"
        
        sub_h1 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1.empty: return "neutral"
        comp = (sub_h1[['ema9','ema21','ema50']].max(axis=1) / sub_h1[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "loose"
        if min_c < 0.4: acc = "micro_squeeze"
        elif min_c < 0.8: acc = "tight_squeeze"
        elif min_c < 1.5: acc = "coiling"
        
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        if sub_d.empty or sub_h4.empty: return "neutral"
        s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
                 sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
                 sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
        ritim = "active" if vol_pulse > 1.0 else "sleeping"
        if vol_pulse > 2.0: ritim = "ignited"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "mid_zone"
        if retr > -20: ctx = "recovery_high"
        elif retr < -50: ctx = "deep_valley"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    # ------------------------------------------------------------
    
    # Store Rallies
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_map = {}
    for r in all_rallies:
        if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']:
            d = pd.Timestamp(r['event_time']).normalize()
            rally_map[d] = {
                'tier': r.get('tier'),
                'gain': r.get('gain', 0) or r.get('pnl', 0)
            }
            
    signals = []
    
    # Scan All Days
    for date in df_d.index:
        dna = get_profile(date)
        if dna in allowed_families:
            target_date = date + pd.Timedelta(days=1)
            if target_date in rally_map:
                r_info = rally_map[target_date]
                signals.append({
                    'signal_date': date.strftime('%Y-%m-%d'),
                    'rally_date': target_date.strftime('%Y-%m-%d'),
                    'tier': r_info['tier'],
                    'gain': r_info['gain']
                })
    
    if not signals:
        print(f"⚠️ No matching signals found during report generation for {symbol}??")
        return

    # Generate MD
    signals.sort(key=lambda x: x['signal_date'])
    
    md = f"# 🚇 {symbol} v4 (SAF TAHMİN) DETAYLI DÖKÜM\n\n"
    md += f"**Toplam Sinyal:** {len(signals)}\n"
    md += f"**Kural:** Sinyal Günü (T=0) -> Ralli Ertesi Gün (T+1)\n\n"
    
    md += "| Sinyal Tarihi | Beklenen Ralli (T+1) | Tip | Kazanç (%) |\n"
    md += "| :--- | :--- | :--- | :--- |\n"
    
    for s in signals:
        icon = "💎" if s['tier'] == 'DIAMOND' else "🥇" if s['tier'] == 'GOLD' else "🥈"
        gain_str = f"%{s['gain']:.2f}" if s['gain'] else "N/A"
        md += f"| {s['signal_date']} | {s['rally_date']} | {icon} {s['tier']} | {gain_str} |\n"
        
    out_path = f"/Users/alisaglam/.gemini/antigravity/brain/74eb5317-8de8-4465-8305-2b29d5903605/{symbol}_v4_detailed_list.md"
    with open(out_path, "w") as f:
        f.write(md)
        
    print(f"✅ Detailed report saved: {out_path}")

if __name__ == "__main__":
    report_v4_details(sys.argv[1])
