
import pandas as pd
import numpy as np
import os
import json
import re

# CONFIG
TARGET_DATE = pd.Timestamp("2026-01-28")
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
TUNEL_FILE = "jan28_tunel_candidates.json"
OUTPUT_FILE = "jan28_aysenti_candidates.json"

def get_profile_simple_dynamic(day, df_w, df_h1, df_d, df_h4):
    try:
        # Standard Profile Logic (simulating "Current State")
        
        # WEEKLY
        sub_w = df_w[df_w.index <= day].tail(30)
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        # HOURLY
        sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        # HARMONY
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        sub_h1_sub = df_h1[df_h1.index <= day]
        
        if sub_d.empty or sub_h4.empty or sub_h1_sub.empty: return "neutral"
        if 'ema21' not in sub_d or 'ema21' not in sub_h4 or 'ema21' not in sub_h1_sub: return "neutral"

        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + \
            int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + \
            int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        # VOLUME & ENERGY
        sub_d_tail = sub_d.tail(10)
        vol_p = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        # CONTEXT
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "neutral"

def run_aysenti():
    # 1. Get Exclude List (Ayaş Tüneli alumni)
    exclude_list = set()
    if os.path.exists(TUNEL_FILE):
        with open(TUNEL_FILE, "r") as f:
            tunel_cands = json.load(f)
            exclude_list = {c['symbol'] for c in tunel_cands}
    
    print(f"🌉 AYSENTİ GEÇİDİ AÇILIYOR... Hedef: {TARGET_DATE}")
    print(f"🚫 Hariç Tutulanlar (Ayaş Mezunları): {len(exclude_list)} Coin")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    candidates = []
    
    for symbol in symbols:
        # SKIP if already in Ayaş
        if symbol in exclude_list: continue

        try:
            key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path): continue
            
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            def load_clean(path):
                if not os.path.exists(path): return pd.DataFrame()
                df = pd.read_parquet(path)
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df = df[~df.index.duplicated(keep='last')]
                return df.sort_index()

            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            if df_1d.empty: continue
            
            # Optimization: Check date range
            if TARGET_DATE > df_1d.index[-1] + pd.Timedelta(days=2): continue

            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")

            if not df_1d.empty: df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            if not df_4h.empty: df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            if not df_1h.empty:
                for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()
            
            # Find Exact Entry Time (Hourly Scan)
            entry_time = None
            detected_dna = None
            
            # Create hourly timestamps for the Target Date
            current_day_start = TARGET_DATE.normalize()
            hourly_range = pd.date_range(start=current_day_start, end=TARGET_DATE, freq='1h')
            
            for check_time in hourly_range:
                # Need to slice data up to check_time for strict realistic checking
                # Check DNA
                d_check = get_profile_simple_dynamic(check_time, df_1w, df_1h, df_1d, df_4h)
                if d_check in golden_dna_list:
                    entry_time = check_time.strftime("%H:%M")
                    detected_dna = d_check
                    break
            
            # If not found during day but found at close (fallback)
            if not entry_time:
                 d_last = get_profile_simple_dynamic(TARGET_DATE, df_1w, df_1h, df_1d, df_4h)
                 if d_last in golden_dna_list:
                     entry_time = "23:59" # Late bloomer
                     detected_dna = d_last
            
            if entry_time and detected_dna:
                candidates.append({
                    "symbol": symbol,
                    "dna": detected_dna,
                    "entry_time": entry_time
                })

        except Exception as e:
            continue

    with open(OUTPUT_FILE, "w") as f:
        json.dump(candidates, f, indent=2)
    
    print(f"🏁 AYSENTİ KAPANDI. {len(candidates)} Coin geçiş izni aldı.")
    print(f"📄 Liste kaydedildi: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_aysenti()
