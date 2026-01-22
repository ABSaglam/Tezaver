import json
import os
import sys
import glob
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core.rally_store import RallyStore

def get_profile_optimized(day, df_w, df_d, df_h4, df_h1):
    # This is slightly optimized but returns the same string
    try:
        # Index filtering is faster when pre-calculated or minimized
        sub_w_at = df_w.index <= day
        if not sub_w_at.any(): return "neutral"
        
        # Weekly info
        last_w = df_w[sub_w_at].iloc[-1]
        
        # Faz (Calculated from EMA/Price or same logic)
        # Re-using the same logic for consistency
        sub_w = df_w[sub_w_at]
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        faz = "neutral"
        if rsi_val < 40: faz = "derin_dip"
        elif rsi_val < 60: faz = "birikim_fazi"
        elif rsi_val < 75: faz = "yukselis_fazi"
        else: faz = "asiri_alim"
        
        # Acc (H1 Squeeze)
        sub_h1_at = df_h1.index <= day
        sub_h1_24 = df_h1[sub_h1_at].tail(24)
        if sub_h1_24.empty: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "loose"
        if min_c < 0.4: acc = "micro_squeeze"
        elif min_c < 0.8: acc = "tight_squeeze"
        elif min_c < 1.5: acc = "coiling"
        
        # Harm
        sub_d_at = df_d.index <= day
        sub_h4_at = df_h4.index <= day
        last_d = df_d[sub_d_at].iloc[-1]
        last_h4 = df_h4[sub_h4_at].iloc[-1]
        last_h1 = df_h1[sub_h1_at].iloc[-1]
        
        s = sum([last_d['close']>last_d['ema21'], 
                last_h4['close']>last_h4['ema21'], 
                last_h1['close']>last_h1['ema21']])
        harm = f"harmony_L{s}"
        
        # Ritim & Enerji
        sub_d_tail = df_d[sub_d_at].tail(10)
        vol_pulse = last_d['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "active" if vol_pulse > 1.0 else "sleeping"
        if vol_pulse > 2.0: ritim = "ignited"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        # Context
        yr_high = df_d[sub_d_at].tail(365)['high'].max() if len(sub_d_tail)>0 else 1
        retr = (last_d['close']/yr_high - 1)*100
        ctx = "mid_zone"
        if retr > -20: ctx = "recovery_high"
        elif retr < -50: ctx = "deep_valley"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except Exception as e:
        return "neutral"

def run_jan_audit():
    print("🔍 JAN 2026 HONEST BLIND AUDIT STARTING (OPTIMIZED)...")
    
    # Load Performance Data
    performance_map = {}
    try:
        with open("data/global_performance_audit.json", "r") as f:
            perf_list = json.load(f)
            for item in perf_list:
                performance_map[item['dna']] = item
    except: pass

    # Range
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 20) # EXTENDED
    test_days = pd.date_range(start_date, end_date)
    test_cutoff = pd.Timestamp(2025, 12, 31)

    key_files = glob.glob("data/golden_keys/*_key.json")
    whitelist = [os.path.basename(f).split('_')[0] for f in key_files]

    report_lines = ["# 🛡️ OCAK 2026 HİYERARŞİK BLIND AUDIT RAPORU\n"]
    report_lines.append(f"**Güncelleme Tarihi:** 21 Ocak 2026\n")
    report_lines.append("**Sınıflandırma:**\n")
    report_lines.append("- **[🛡️ İMZA]**: Koin bu kapıyı (DNA) geçmişte en az 1 kez başarıyla kullandı.\n")
    report_lines.append("- **[📡 RADAR]**: Koin bu kapıyı ilk defa deniyor; başarısı market geneli istatistiğine dayanıyor.\n\n")

    # Day-to-Signals Map
    daily_signals = {d.strftime('%Y-%m-%d'): [] for d in test_days}

    total = len(whitelist)
    for i, symbol in enumerate(whitelist, 1):
        print(f"[{i}/{total}] Analyzing {symbol}...")
        try:
            df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
            df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
            df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
            df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")

            for df in [df_w, df_d, df_h4, df_h1]:
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df.sort_index(inplace=True)
                df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
                df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
                df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

            store = RallyStore()
            all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
            rally_map = {pd.Timestamp(r['event_time']).normalize(): r for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}
            
            with open(f"data/golden_keys/{symbol}_key.json", "r") as f:
                key_data = json.load(f)
                allowed_dna = set(key_data.get('golden_dna_list', []))

            # Hit & Performance Counting
            dna_stats = {} # DNA -> {hits, total_gain}
            
            for hist_date in df_d.index:
                if hist_date > test_cutoff: break
                profile = get_profile_optimized(hist_date, df_w, df_d, df_h4, df_h1)
                if profile in allowed_dna:
                    target_day = hist_date + timedelta(days=1)
                    if target_day in rally_map:
                        r = rally_map[target_day]
                        gain = r.get('raw_data', {}).get('gain', 0)
                        if profile not in dna_stats: dna_stats[profile] = {'hits': 0, 'gains': []}
                        dna_stats[profile]['hits'] += 1
                        dna_stats[profile]['gains'].append(gain)
            
            # Now Check Test Period
            for current_day in test_days:
                if current_day not in df_d.index: continue
                profile = get_profile_optimized(current_day, df_w, df_d, df_h4, df_h1)
                
                if profile in allowed_dna and profile != "neutral":
                    actual_gain = "WAITING"
                    target_day = current_day + timedelta(days=1)
                    if target_day in df_d.index:
                        signal_close = df_d.loc[current_day, 'close']
                        target_high = df_d.loc[target_day, 'high']
                        gain_pct = (target_high / signal_close - 1) * 100
                        actual_gain = f"%{gain_pct:.2f}"

                    perf = performance_map.get(profile, {})
                    local_info = dna_stats.get(profile, {'hits': 0, 'gains': [0]})
                    local_avg = f"%{sum(local_info['gains'])/len(local_info['gains']):.2f}" if local_info['hits'] > 0 else "YENİ"
                    
                    sig_type = "[🛡️ İMZA]" if local_info['hits'] > 0 else "[📡 RADAR]"

                    daily_signals[current_day.strftime('%Y-%m-%d')].append({
                        'symbol': symbol,
                        'type': sig_type,
                        'dna': profile,
                        'local_hits': local_info['hits'],
                        'local_avg': local_avg,
                        'global_avg': f"%{perf.get('avg_gain', 0):.2f}",
                        'actual': actual_gain
                    })
        except: continue

    # Report Gen
    for day_str in daily_signals:
        signals = daily_signals[day_str]
        if not signals: continue
        
        target_str = (datetime.strptime(day_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        report_lines.append(f"### 📅 {day_str} Gece Kapanışı (Hedef: {target_str})\n")
        report_lines.append("| Koin | Tür | Yerel İsabet | **Lok. Ort%** | **Glo. Ort%** | **Gerçek Sonuç** |\n")
        report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |\n")
        
        signals.sort(key=lambda x: x['local_hits'], reverse=True)
        for s in signals:
            report_lines.append(f"| {s['symbol']} | {s['type']} | {s['local_hits']} | **{s['local_avg']}** | **{s['global_avg']}** | **{s['actual']}** |\n")
        report_lines.append("\n")

    with open("JAN_2026_HONEST_AUDIT.md", "w") as f:
        f.writelines(report_lines)
    print("🏁 Optimized Audit Completed.")

if __name__ == "__main__":
    run_jan_audit()
