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

def analyze_coin_honesty(symbol):
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
        df_h4 = load_df('4h')
        df_h1 = load_df('1h')
        
        # 1. Identify Pre-2026 Identities (Dürüst Geçmiş)
        store = RallyStore()
        all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
        success_rally_dates = {pd.Timestamp(r['event_time']).normalize() for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}
        
        pre_2026_cutoff = pd.Timestamp(2025, 12, 31)
        pre_2026_identities = set()
        
        # Optimization: Only calculate DNA for days followed by a SUCCESS rally
        for rally_day in success_rally_dates:
            if rally_day > pre_2026_cutoff + timedelta(days=1): continue # Rally can be on Jan 1st if signal was on Dec 31st
            
            signal_day = rally_day - timedelta(days=1)
            if signal_day not in df_d.index: continue
            
            dna = get_profile(signal_day, df_w, df_d, df_h4, df_h1)
            if dna != "neutral":
                pre_2026_identities.add(dna)
        
        # 2. Analyze January 2026
        results = []
        jan_dates = pd.date_range(datetime(2026, 1, 1), datetime(2026, 1, 21))
        
        # Total rallies in Jan for gain check
        jan_rallies = [r for r in all_rallies if pd.Timestamp(r['event_time']) >= pd.Timestamp(2026, 1, 1)]
        
        for current_day in jan_dates:
            if current_day not in df_d.index: continue
            
            profile = get_profile(current_day, df_w, df_d, df_h4, df_h1)
            if profile == "neutral": continue
            
            # Is it in the CURRENT golden list? (v4 protocol check)
            with open(f"data/golden_keys/{symbol}_key.json", "r") as f:
                current_allowed = set(json.load(f).get('golden_dna_list', []))
            
            if profile not in current_allowed: continue
            
            # Label: Identity vs Radar (The Honesty Filter)
            sig_type = "[🛡️ İMZA]" if profile in pre_2026_identities else "[📡 RADAR]"
            
            # Actual Outcome
            target_start = current_day
            target_end = current_day + timedelta(hours=48)
            
            actual_tier = "FAIL"
            max_gain = 0
            
            # Gain check
            subset_h1 = df_h1[(df_h1.index > target_start) & (df_h1.index <= target_end)]
            if not subset_h1.empty:
                max_gain = (subset_h1['high'].max() / df_d.loc[current_day, 'close'] - 1) * 100
            
            for r in all_rallies:
                r_time = pd.Timestamp(r['event_time'])
                if target_start < r_time <= target_end:
                    if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']:
                        actual_tier = r['tier']
                        break
            
            results.append({
                'day': current_day.strftime('%Y-%m-%d'),
                'symbol': symbol,
                'type': sig_type,
                'dna': profile,
                'max_gain': f"%{max_gain:.2f}",
                'result': actual_tier
            })
            
        return results
    except Exception as e:
        # print(f"Error in {symbol}: {str(e)}")
        return []

def run_pure_audit():
    print("🎬 STARTING PURE IDENTITY JANUARY AUDIT (ARINMIŞ DENETİM)...")
    key_files = glob.glob("data/golden_keys/*_key.json")
    symbols = [os.path.basename(f).split('_')[0] for f in key_files]
    
    cpu_count = mp.cpu_count()
    print(f"🧬 Analyzing {len(symbols)} symbols with {cpu_count} cores...")
    
    with mp.Pool(cpu_count) as pool:
        all_res_lists = pool.map(analyze_coin_honesty, symbols)
    
    all_signals = [item for sublist in all_res_lists for item in sublist]
    all_signals.sort(key=lambda x: (x['day'], x['symbol']))
    
    # Report Generation
    report = ["# 🛡️ AYAŞ TÜNELİ v4: OCAK 2026 ARINMIŞ (PURE IDENTITY) DENETİM RAPORU\n"]
    report.append(f"**Oluşturulma:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    report.append("**Tanımlama:**\n")
    report.append("- **[🛡️ İMZA]**: Bu DNA, koinin tarihinde 1 Ocak 2026 öncesinde en az 1 kez ralli başlatmıştır. (DÜRÜST)\n")
    report.append("- **[📡 RADAR]**: Bu DNA, koinin tarihinde ilk defa Ocak 2026'da görülmüştür. (SIZINTI/DENEYSEL)\n\n")

    report.append("## 🚩 BÖLÜM 1: SIZINTI VE KÖR TEST TÜM SİNYALLER\n")
    report.append("| Tarih | Koin | Tür | DNA (Kapı) | Max % (15D) | Gerçek Sonuç |\n")
    report.append("| :--- | :--- | :---: | :--- | :---: | :---: |\n")
    
    for s in all_signals:
        report.append(f"| {s['day']} | {s['symbol']} | {s['type']} | `{s['dna']}` | **{s['max_gain']}** | **{s['result']}** |\n")
        
    # Stats Header
    report.append("\n---\n\n")
    report.append("## 📊 İSTATİSTİKSEL ÖZET (HONESTY CHECK)\n")
    
    # Calculate Stats
    def get_stats(signals):
        total = len(signals)
        if total == 0: return "Veri yok"
        identities = [x for x in signals if x['type'] == "[🛡️ İMZA]"]
        radars = [x for x in signals if x['type'] == "[📡 RADAR]"]
        
        id_success = [x for x in identities if x['result'] != "FAIL"]
        rd_success = [x for x in radars if x['result'] != "FAIL"]
        
        res = f"- Toplam Sinyal: {total}\n"
        res += f"- Saf İmzalar [🛡️ İMZA]: {len(identities)} (Başarı: {len(id_success)}/{len(identities)})\n"
        res += f"- Radar Sızıntılar [📡 RADAR]: {len(radars)} (Başarı: {len(rd_success)}/{len(radars)})\n"
        return res

    leak_signals = [s for s in all_signals if s['day'] <= '2026-01-16']
    blind_signals = [s for s in all_signals if s['day'] > '2026-01-16']

    report.append("### 1-17 Ocak (Sızıntı Bölgesi) Karnesi\n")
    report.append(get_stats(leak_signals))
    
    report.append("\n### 18-22 Ocak (Gerçek Kör Test) Karnesi\n")
    report.append(get_stats(blind_signals))
    
    with open("JAN_2026_PURE_IDENTITY_AUDIT.md", "w") as f:
        f.writelines(report)
        
    print(f"✅ Audit Completed. Found {len(all_signals)} total signals.")
    print("📜 Report: JAN_2026_PURE_IDENTITY_AUDIT.md")

if __name__ == "__main__":
    run_pure_audit()
