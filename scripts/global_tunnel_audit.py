import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# CONFIG
START_DATE = pd.Timestamp("2025-12-01")
END_DATE = pd.Timestamp("2026-01-23")
COIN_CELLS_DIR = "coin_cells"

def get_profile_simple(day, df_w, df_h1, df_d, df_h4):
    try:
        # Weekly RSI for Faz
        sub_w = df_w[df_w.index <= day].tail(30)
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        # H1 Squeeze for Acc
        sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        # Harmony
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        sub_h1_sub = df_h1[df_h1.index <= day]
        if sub_d.empty or sub_h4.empty or sub_h1_sub.empty: return "neutral"
        
        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        # Ritim (Volume Pulse)
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_pulse > 2.0 else "active" if vol_pulse > 1.0 else "sleeping"
        
        # Enerji
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        # Context (Recovery/Valley)
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "neutral"

def global_tunnel_audit():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    all_passed_days = []

    for symbol in symbols:
        try:
            # Load Golden Key
            key_path = f"data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path): continue
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            # Load Data
            df_1d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
            df_1d['dt'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
            df_1d.set_index('dt', inplace=True)
            df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            
            df_1w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
            df_1w['dt'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
            df_1w.set_index('dt', inplace=True)
            
            df_4h = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
            df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
            df_4h.set_index('dt', inplace=True)
            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            
            df_1h = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
            df_1h['dt'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
            df_1h.set_index('dt', inplace=True)
            df_1h['ema9'] = df_1h['close'].ewm(span=9, adjust=False).mean()
            df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
            df_1h['ema50'] = df_1h['close'].ewm(span=50, adjust=False).mean()

            df_15m = pd.read_parquet(f"coin_cells/{symbol}/data/history_15m.parquet")
            df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            df_15m.set_index('dt', inplace=True)

            # Loop Days
            current = START_DATE
            while current <= END_DATE:
                dna = get_profile_simple(current, df_1w, df_1h, df_1d, df_4h)
                if dna in golden_dna_list:
                    day_data = df_15m[df_15m.index.normalize() == current]
                    if not day_data.empty:
                        rally = (day_data['high'].max() / day_data['low'].min() - 1) * 100
                        all_passed_days.append({
                            'date': current,
                            'symbol': symbol,
                            'rally': rally,
                            'dna': dna
                        })
                current += pd.Timedelta(days=1)
        except Exception as e:
            continue

    # Sort and Report
    report_df = pd.DataFrame(all_passed_days)
    if report_df.empty:
        print("Tünelden geçen gün bulunamadı.")
        return

    # Sort by Date ascending, then Rally descending
    report_df.sort_values(by=['date', 'rally'], ascending=[True, False], inplace=True)

    print("# 🕵️ GLOBAL TÜNEL DENETİM RAPORU (1 ARALIK 2025 - GÜNÜMÜZ)")
    
    current_date = None
    for _, row in report_df.iterrows():
        day_str = row['date'].strftime("%d %B %Y")
        if day_str != current_date:
            print(f"\n## 📅 {day_str}")
            print("| COIN | RALLİ BOYU (%) | DNA PROFİLİ |")
            print("| --- | --- | --- |")
            current_date = day_str
        
        print(f"| {row['symbol']} | %{row['rally']:.2f} | `{row['dna']}` |")

if __name__ == "__main__":
    global_tunnel_audit()
