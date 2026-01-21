import json
import os
import glob
import pandas as pd
from tezaver.core.rally_store import RallyStore
from collections import Counter

def get_profile(day, df_w, df_d, df_h4, df_h1):
    # This must match report_v4_details.py and mass_v4_production.py EXACTLY
    sub_w = df_w[df_w.index <= day]
    if sub_w.empty: return "neutral"
    
    # Faz (Weekly RSI)
    delta = sub_w['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
    rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    
    faz = "neutral"
    if rsi_val < 40: faz = "derin_dip"
    elif rsi_val < 60: faz = "birikim_fazi"
    elif rsi_val < 75: faz = "yukselis_fazi"
    else: faz = "asiri_alim"
    
    # Acc (H1 Squeeze) - 24h lookback
    sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
    if sub_h1_24.empty: return "neutral"
    comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
    min_c = comp.min()
    acc = "loose"
    if min_c < 0.4: acc = "micro_squeeze"
    elif min_c < 0.8: acc = "tight_squeeze"
    elif min_c < 1.5: acc = "coiling"
    
    # Harm (D/H4/H1 EMA21 Harmony)
    sub_d = df_d[df_d.index <= day]
    sub_h4 = df_h4[df_h4.index <= day]
    sub_h1 = df_h1[df_h1.index <= day]
    if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral"
    s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
             sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
             sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
    harm = f"harmony_L{s}"
    
    # Ritim (Daily Vol Pulse)
    sub_d_tail = sub_d.tail(10)
    vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
    ritim = "active" if vol_pulse > 1.0 else "sleeping"
    if vol_pulse > 2.0: ritim = "ignited"
    
    # Enerji (Volume Trend)
    v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
    enerji = "building_energy" if v_trend else "depleting_energy"
    
    # Context (Yearly Retracement)
    yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
    retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
    ctx = "mid_zone"
    if retr > -20: ctx = "recovery_high"
    elif retr < -50: ctx = "deep_valley"
    
    return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

def run_performance_audit():
    print("🚀 GLOBAL PERFORMANCE AUDIT (STAGE 4) STARTING...")
    
    key_files = glob.glob("data/golden_keys/*_key.json")
    store = RallyStore()
    
    dna_stats = {} # dna -> {gain: sum, diam: count, gold: count, silv: count, total: count}

    for idx, file_path in enumerate(key_files):
        symbol = os.path.basename(file_path).split('_')[0]
        print(f"[{idx+1}/{len(key_files)}] Analyzing {symbol}...")
        
        try:
            with open(file_path, "r") as f:
                key_data = json.load(f)
            
            allowed_dna = set(key_data.get('golden_dna_list', []))
            if not allowed_dna: continue

            # Load Data
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

            # Load Rallies
            rallies = store.list_rallies(symbol=symbol, timeframe='15m')
            
            # Match Rallies to DNA and T-1 Profiles
            for r in rallies:
                tier = r.get('tier')
                if tier not in ['DIAMOND', 'GOLD', 'SILVER']: continue
                
                # Signal date is T-1 relative to rally date
                rally_day = pd.Timestamp(r['event_time']).normalize()
                signal_day = rally_day - pd.Timedelta(days=1)
                
                if signal_day not in df_d.index: continue
                
                profile = get_profile(signal_day, df_w, df_d, df_h4, df_h1)
                
                if profile in allowed_dna:
                    if profile not in dna_stats:
                        dna_stats[profile] = {'gain': 0, 'DIAMOND': 0, 'GOLD': 0, 'SILVER': 0, 'total': 0}
                    
                    raw = r.get('raw_data', {})
                    gain = raw.get('gain', 0) or r.get('gain', 0) or 0
                    dna_stats[profile]['gain'] += gain
                    dna_stats[profile][tier] += 1
                    dna_stats[profile]['total'] += 1

        except Exception as e:
            print(f"⚠️ Skipping {symbol} due to error: {e}")

    # Process Stats
    final_leaderboard = []
    for dna, stats in dna_stats.items():
        avg_gain = stats['gain'] / stats['total'] if stats['total'] > 0 else 0
        final_leaderboard.append({
            'dna': dna,
            'total_hits': stats['total'],
            'avg_gain': round(avg_gain, 2),
            'diamond_count': stats['DIAMOND'],
            'gold_count': stats['GOLD'],
            'silver_count': stats['SILVER'],
            'power_score': round(avg_gain * stats['total'], 2) # Frequency * Quality
        })

    # Sort by Power Score
    final_leaderboard.sort(key=lambda x: x['power_score'], reverse=True)

    output_path = "data/global_performance_audit.json"
    with open(output_path, "w") as f:
        json.dump(final_leaderboard, f, indent=2)

    print(f"🏁 Performance Audit Complete. Results saved to {output_path}")

    # Generate Report
    report_path = "GLOBAL_PERFORMANCE_LEADERBOARD.md"
    with open(report_path, "w") as f:
        f.write("# 🏆 GLOBAL PERFORMANCE LEADERBOARD: THE ELITE GATES\n\n")
        f.write("Bu tablo, market genelinde en kârlı ve en sık ralli yakalayan 'Altın DNA'ları listeler.\n\n")
        f.write("| DNA (Profil) | Hits | Avg % | 💎 | 🥇 | 🥈 | Power Score |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for item in final_leaderboard[:50]: # Top 50
            f.write(f"| `{item['dna']}` | {item['total_hits']} | %{item['avg_gain']} | {item['diamond_count']} | {item['gold_count']} | {item['silver_count']} | {item['power_score']} |\n")

if __name__ == "__main__":
    run_performance_audit()
