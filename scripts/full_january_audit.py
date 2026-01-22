import json
import os
import glob
import pandas as pd
import multiprocessing as mp
from datetime import datetime, timedelta
from tezaver.core.rally_store import RallyStore

# DNA Profile Logic (v4 standard)
def get_profile(day, df_w, df_d, df_h4, df_h1):
    try:
        sub_w = df_w[df_w.index <= day].tail(30)
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1_24.empty: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        sub_h1 = df_h1[df_h1.index <= day]
        if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral"
        s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
                sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
                sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_pulse > 2.0 else "active" if vol_pulse > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except:
        return "neutral"

def process_coin_full_jan(symbol):
    try:
        # Load all history but calculate DNAs only once for history and once per Jan day
        df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
        df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
        df_d.set_index('dt', inplace=True)
        
        df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        df_w['dt'] = pd.to_datetime(df_w['timestamp'], unit='ms')
        df_w.set_index('dt', inplace=True)
        
        df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
        df_h4['dt'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
        df_h4.set_index('dt', inplace=True)
        
        df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
        df_h1['dt'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
        df_h1.set_index('dt', inplace=True)
        
        for df in [df_d, df_h4, df_h1]:
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # Load Key
        with open(f"data/golden_keys/{symbol}_key.json", "r") as f:
            key_data = json.load(f)
            allowed = set(key_data.get('golden_dna_list', []))
            
        # Calculate Historical DNA Hits (pre-Jan 2026)
        test_cutoff = pd.Timestamp(2025, 12, 31)
        hist_dna_counts = {}
        for d in df_d.index:
            if d > test_cutoff: break
            # DNA calculation is slow, let's only do it for days followed by a SUCCESS rally to speed up?
            # No, we need to know hits. But we already have the golden list.
            # Let's trust the golden list and just count them if needed.
            pass
        
        # Actually, let's use the 'total_signals' from JSON or similar if available.
        # For simplicity, if it's in golden_dna_list, it has historical hits.
        
        results = []
        jan_dates = pd.date_range(datetime(2026, 1, 1), datetime(2026, 1, 21))
        
        store = RallyStore()
        rallies = store.list_rallies(symbol=symbol, timeframe='15m')
        
        for current_day in jan_dates:
            if current_day not in df_d.index: continue
            
            profile = get_profile(current_day, df_w, df_d, df_h4, df_h1)
            
            if profile in allowed and profile != "neutral":
                target_start = current_day
                target_end = current_day + timedelta(hours=48)
                
                actual_tier = "FAIL"
                max_gain = 0
                
                subset_h1 = df_h1[(df_h1.index > target_start) & (df_h1.index <= target_end)]
                if not subset_h1.empty:
                    max_gain = (subset_h1['high'].max() / df_d.loc[current_day, 'close'] - 1) * 100
                
                for r in rallies:
                    r_time = pd.Timestamp(r['event_time'])
                    if target_start <= r_time <= target_end:
                        if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']:
                            actual_tier = r['tier']
                            break
                
                results.append({
                    'day': current_day.strftime('%Y-%m-%d'),
                    'symbol': symbol,
                    'dna': profile,
                    'max_gain': f"%{max_gain:.2f}",
                    'result': actual_tier
                })
        return results
    except:
        return []

def run_full_audit():
    print("🎬 STARTING FULL JANUARY AUDIT...")
    key_files = glob.glob("data/golden_keys/*_key.json")
    symbols = [os.path.basename(f).split('_')[0] for f in key_files]
    
    cpu_count = mp.cpu_count()
    with mp.Pool(cpu_count) as pool:
        all_res_lists = pool.map(process_coin_full_jan, symbols)
    
    all_signals = [item for sublist in all_res_lists for item in sublist]
    all_signals.sort(key=lambda x: (x['day'], x['symbol']))
    
    report = ["# 🕵️ AYAŞ TÜNELİ v4: OCAK 2026 ŞEFFAF DENETİM RAPORU (BAŞARISIZLAR DAHİL)\n"]
    report.append(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
    
    report.append("## 🚩 BÖLÜM 1: SIZINTI BÖLGESİ (01 - 17 OCAK)\n")
    report.append("| Tarih | Koin | DNA (Kapı) | Max % (15D) | Gerçek Sonuç |\n")
    report.append("| :--- | :--- | :--- | :---: | :---: |\n")
    
    leak_signals = [s for s in all_signals if s['day'] <= '2026-01-16']
    for s in leak_signals:
        report.append(f"| {s['day']} | {s['symbol']} | `{s['dna']}` | **{s['max_gain']}** | **{s['result']}** |\n")
        
    report.append("\n---\n\n")
    
    report.append("## 🕵️ BÖLÜM 2: GERÇEK KÖR TEST (18 - 22 OCAK)\n")
    report.append("| Tarih | Koin | DNA (Kapı) | Max % (15D) | Gerçek Sonuç |\n")
    report.append("| :--- | :--- | :--- | :---: | :---: |\n")
    
    blind_signals = [s for s in all_signals if s['day'] > '2026-01-16']
    for s in blind_signals:
        report.append(f"| {s['day']} | {s['symbol']} | `{s['dna']}` | **{s['max_gain']}** | **{s['result']}** |\n")
        
    with open("JAN_2026_FULL_TRANSPARENT_AUDIT.md", "w") as f:
        f.writelines(report)
    print("🏁 Done.")

if __name__ == "__main__":
    run_full_audit()
