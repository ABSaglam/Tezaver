import json
import os
import glob
import pandas as pd
from datetime import datetime, timedelta

def get_profile(day, df_w, df_d, df_h4, df_h1):
    # DİKKAT: Bu fonksiyon mass_v4_production.py ve report_v4_details.py ile BİREBİR aynı olmalıdır.
    try:
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
    except:
        return "neutral"

import argparse

def run_blind_test():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="Signal date (YYYY-MM-DD). Prediction will be for the next day.")
    args = parser.parse_args()

    print("🔮 BLIND V4 PREDICTION (THE FIRE TRIAL) STARTING...")
    
    # Load Performance Data for Quality Check
    performance_map = {}
    try:
        with open("data/global_performance_audit.json", "r") as f:
            perf_list = json.load(f)
            for item in perf_list:
                performance_map[item['dna']] = item
    except:
        print("⚠️ DNA Performance data not found. Stats will be empty.")

    if args.day:
        test_days = [datetime.strptime(args.day, '%Y-%m-%d')]
    else:
        test_days = [
            datetime(2026, 1, 17), # Targets Jan 18
            datetime(2026, 1, 18), # Targets Jan 19
            datetime(2026, 1, 19), # Targets Jan 20
            datetime(2026, 1, 20), # Targets Jan 21
            datetime(2026, 1, 21)  # Targets Jan 22 (TODAY)
        ]

    key_files = glob.glob("data/golden_keys/*_key.json")
    whitelist = [os.path.basename(f).split('_')[0] for f in key_files]

    report_name = f"BLIND_PREDICTION_REPORT_{args.day if args.day else 'LATEST'}.md"
    report_lines = ["# 🔮 AYAŞ TÜNELİ v4: KÖR TEST TAHMİN RAPORU (BLIND PREDICTIONS)\n"]
    report_lines.append(f"**Oluşturulma Tarihi:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append("**Yöntem:** Koinlerin kendi 'Altın Anahtarları' + Market Geneli Performans İstatistikleri\n\n")
    report_lines.append("---\n")

    for signal_date in test_days:
        target_date = signal_date + timedelta(days=1)
        day_str = signal_date.strftime('%Y-%m-%d')
        target_str = target_date.strftime('%Y-%m-%d')
        
        print(f"\n📅 Calculating for {day_str} night (Prediction for {target_str})...")
        report_lines.append(f"## 📅 {day_str} Kapanışı Sinyalleri (Hedef: {target_str})\n\n")
        report_lines.append("| Koın | Tespit Edilen DNA (Kapı) | Historik İsabet | Ort. % | 💎|🥇|🥈 | Power Score |\n")
        report_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        
        signals_found = 0
        for symbol in whitelist:
            key_path = f"data/golden_keys/{symbol}_key.json"
            try:
                with open(key_path, "r") as f:
                    key_data = json.load(f)
                    allowed_dna = set(key_data.get('golden_dna_list', []))
                
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

                # Search by finding exact index or closest match before
                if signal_date not in df_d.index:
                    # In case of manual run with slightly different time, let's try normalized date
                    if pd.Timestamp(signal_date).normalize() in df_d.index:
                        signal_date = pd.Timestamp(signal_date).normalize()
                    else: continue
                
                profile = get_profile(signal_date, df_w, df_d, df_h4, df_h1)
                
                if profile in allowed_dna and profile != "neutral":
                    perf = performance_map.get(profile, {})
                    hits = perf.get('total_hits', 0)
                    avg = perf.get('avg_gain', 0)
                    diam = perf.get('diamond_count', 0)
                    gold = perf.get('gold_count', 0)
                    silv = perf.get('silver_count', 0)
                    score = perf.get('power_score', 0)
                    
                    report_lines.append(f"| {symbol} | `{profile}` | {hits} | %{avg} | {diam} | {gold} | {silv} | {score} |\n")
                    signals_found += 1
            except:
                continue
        
        if signals_found == 0:
            report_lines.append("| - | Bu gece tünelden geçen koin olmadı. | - | - | - | - | - | - |\n")
        
        report_lines.append("\n---\n")

    with open(report_name, "w") as f:
        f.writelines(report_lines)
    
    print(f"\n🏁 Blind Test Report Generated: {report_name}")

if __name__ == "__main__":
    run_blind_test()

if __name__ == "__main__":
    run_blind_test()
