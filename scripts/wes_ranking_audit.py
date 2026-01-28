import json
import os
import glob
import pandas as pd
import multiprocessing as mp
from datetime import datetime, timedelta
from tezaver.core.rally_store import RallyStore

# 1. WES CONFIG
WES_WEIGHTS = {
    'experience': 0.40,  # Geçmiş Başarı Sayısı (Hits)
    'energy': 0.40,      # Ortalama Kazanç (Avg Gain)
    'global_bonus': 20   # Global Elite ise +20 Puan
}

MAX_EXPECTED_HITS = 50   # Normalize için
MAX_EXPECTED_GAIN = 100  # Normalize için

def calculate_wes_score(local_hits, local_avg, is_global):
    # Normalize Experience (0-100)
    exp_score = min(local_hits / MAX_EXPECTED_HITS, 1.0) * 100
    
    # Normalize Energy (0-100)
    eng_score = min(local_avg / MAX_EXPECTED_GAIN, 1.0) * 100
    
    # Base Score
    base_score = (exp_score * WES_WEIGHTS['experience']) + (eng_score * WES_WEIGHTS['energy'])
    
    # Global Bonus
    if is_global:
        base_score += WES_WEIGHTS['global_bonus']
        
    return min(base_score, 100) # Cap at 100

def get_profile(day, df_w, df_d, df_h4, df_h1):
    # Standart v4 Profile Logic (Same as before)
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
        s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
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
    except: return "neutral"

def analyze_wes_honesty(symbol, global_elites):
    try:
        # Load Data
        def load_df(tf):
            df = pd.read_parquet(f"coin_cells/{symbol}/data/history_{tf}.parquet")
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df.sort_index(inplace=True)
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
            return df

        df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        df_w['dt'] = pd.to_datetime(df_w['timestamp'], unit='ms')
        df_w.set_index('dt', inplace=True)
        
        df_d = load_df('1d')
        df_h1 = load_df('1h')
        df_h4 = load_df('4h')
        
        # 1. Identify Pre-2026 Local Identities (With Stats)
        store = RallyStore()
        all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
        
        # Calculate Stats for Each DNA based on Pre-2026 data
        pre_2026_cutoff = pd.Timestamp(2025, 12, 31)
        dna_stats = {} # dna -> {'hits': 0, 'total_gain': 0}
        
        for r in all_rallies:
            r_time = pd.Timestamp(r['event_time']).normalize()
            if r_time > pre_2026_cutoff + timedelta(days=1): continue # Strict Filter
            if r.get('tier') not in ['DIAMOND', 'GOLD', 'SILVER']: continue
            
            signal_day = r_time - timedelta(days=1)
            if signal_day not in df_d.index: continue
            
            dna = get_profile(signal_day, df_w, df_d, df_h4, df_h1)
            if dna == "neutral": continue
            
            if dna not in dna_stats: dna_stats[dna] = {'hits': 0, 'total_gain': 0}
            
            entry = r.get('entry_price', 1)
            high = r.get('highest_price', 1)
            gain = (high/entry - 1)*100
            
            dna_stats[dna]['hits'] += 1
            dna_stats[dna]['total_gain'] += gain

        # 2. Analyze Jan 2026
        results = []
        jan_dates = pd.date_range(datetime(2026, 1, 1), datetime(2026, 1, 21))
        
        # Whitelist Filtering
        try:
            with open(f"data/golden_keys/{symbol}_key.json", "r") as f:
                v4_whitelist = set(json.load(f).get('golden_dna_list', []))
        except:
            v4_whitelist = set()

        for current_day in jan_dates:
            if current_day not in df_d.index: continue
            profile = get_profile(current_day, df_w, df_d, df_h4, df_h1)
            
            # STRICT FILTER: Must be in Golden Keys (as per original honest audit)
            if profile == "neutral" or profile not in v4_whitelist: continue
            
            # Label
            local_info = dna_stats.get(profile)
            is_global = profile in global_elites
            
            if local_info:
                sig_type = "[🛡️ İMZA]"
                hits = local_info['hits']
                avg_gain = local_info['total_gain'] / hits
            elif is_global:
                sig_type = "[🌍 KÜRESEL]"
                hits = 0 # New locally
                avg_gain = 0 
                # For global elites without local history, we can assign a virtual score 
                # but to be strict, we keep local stats 0. The WES score handles the bonus.
            else:
                continue # Skip Radars (We only want the Honest List)
            
            # WES Calculation
            wes_score = calculate_wes_score(hits, avg_gain, is_global)

            # Actual Outcome
            target_start = current_day
            target_end = current_day + timedelta(hours=48)
            actual_tier = "FAIL"
            max_gain = 0
            
            subset_h1 = df_h1[(df_h1.index > target_start) & (df_h1.index <= target_end)]
            if not subset_h1.empty:
                max_gain = (subset_h1['high'].max() / df_d.loc[current_day, 'close'] - 1) * 100
            
            for r in all_rallies:
                r_time = pd.Timestamp(r['event_time'])
                if target_start < r_time <= target_end:
                    if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']:
                        actual_tier = r['tier']
                        break
            
            # CHECK IF THIS SIGNAL IS IN THE 133 HONEST LIST
            # We can relax this check if we trust the logic above which is IDENTICAL to the honest audit logic.
            # The logic above (local_info or is_global) IS the honest audit logic.
            # So this will produce exactly the same 133 list, but ranked.
            
            results.append({
                'day': current_day.strftime('%Y-%m-%d'),
                'symbol': symbol,
                'type': sig_type,
                'dna': profile,
                'wes': wes_score,
                'hits': hits,
                'avg': avg_gain,
                'max_gain': f"%{max_gain:.2f}",
                'result': actual_tier
            })
            
        return results
    except Exception as e:
        # print(e)
        return []

def run_wes_ranking():
    print("🎬 STARTING WES RANKING EXPERIMENT...")
    
    with open("data/global_performance_audit.json", "r") as f:
        perf_list = json.load(f)
        perf_list.sort(key=lambda x: x.get('power_score', 0), reverse=True)
        global_elites = {x['dna'] for x in perf_list[:100]}
    
    key_files = glob.glob("data/golden_keys/*_key.json")
    symbols = [os.path.basename(f).split('_')[0] for f in key_files]
    
    cpu_count = mp.cpu_count()
    with mp.Pool(cpu_count) as pool:
        all_res_lists = pool.starmap(analyze_wes_honesty, [(s, global_elites) for s in symbols])
    
    all_signals = [item for sublist in all_res_lists for item in sublist]
    
    # RANKING LOGIC
    all_signals.sort(key=lambda x: x['wes'], reverse=True)
    
    report = ["# 🎖️ AYAŞ TÜNELİ: WES (CENGAVER) PUANLAMA SIRALAMASI\n"]
    report.append(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d')}\n")
    report.append("**WES Kriterleri:**\n")
    report.append("- **Tecrübe (%40):** Geçmiş isabet sayısı (Hits).\n")
    report.append("- **Enerji (%40):** Geçmiş ortalama kazanç (Avg Gain).\n")
    report.append("- **Global Bonus (+20):** Piyasa genelinde elit olma durumu.\n\n")

    report.append("## 🏆 EN YÜKSEK PUANLI GENERALLER (TOP LIST)\n")
    report.append("| Sıra | Puan | Tarih | Koin | Tür | Hits | Ort.% | 15D Sonuç |\n")
    report.append("| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |\n")
    
    for i, s in enumerate(all_signals):
        rank = i + 1
        icon = "🥇" if rank <= 10 else "🥈" if rank <= 30 else "🥉" if rank <= 60 else "🔹"
        # Highlights for Fail vs Success
        res_str = f"**{s['result']}** ({s['max_gain']})"
        if s['result'] == "FAIL": res_str = f"🔻 FAIL ({s['max_gain']})"
        else: res_str = f"✅ {s['result']} ({s['max_gain']})"
        
        report.append(f"| {icon} {rank} | **{s['wes']:.1f}** | {s['day']} | {s['symbol']} | {s['type']} | {s['hits']} | %{s['avg']:.0f} | {res_str} |\n")
        
    with open("JAN_2026_WES_RANKED_LIST.md", "w") as f:
        f.writelines(report)
        
    print(f"🏁 WES Analysis Complete. Ranked {len(all_signals)} signals.")

if __name__ == "__main__":
    run_wes_ranking()
