
import pandas as pd
import numpy as np
import os
import json
import re

# CONFIG
TARGET_DATE = pd.Timestamp("2026-01-28 00:00:00")
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_FILE = "jan28_tunel_candidates.json"

def get_profile_simple_strict(df_w, df_h1, df_d, df_h4):
    try:
        # STRICT FILTER: Use only data BEFORE Target Date (Yesterday's Close)
        # Assuming DFs are already sliced to < TARGET_DATE
        
        # WEEKLY
        sub_w = df_w.tail(30)
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        # HOURLY (Squeeze)
        sub_h1_24 = df_h1.tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        # HARMONY
        if df_d.empty or df_h4.empty or df_h1.empty: return "neutral"
        
        # Ensure EMAs exist
        if 'ema21' not in df_d or 'ema21' not in df_h4 or 'ema21' not in df_h1: return "neutral"

        s = int(df_d.iloc[-1]['close']>df_d.iloc[-1]['ema21']) + \
            int(df_h4.iloc[-1]['close']>df_h4.iloc[-1]['ema21']) + \
            int(df_h1.iloc[-1]['close']>df_h1.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        # VOLUME & ENERGY
        sub_d_tail = df_d.tail(10)
        vol_p = df_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        # CONTEXT
        yr_high = df_d.tail(365)['high'].max() if len(df_d)>0 else 1
        retr = (df_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except Exception as e:
        # print(f"DEBUG: Profile error: {e}")
        return "neutral"

def run_tunel():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    candidates = []
    
    print(f"🚇 AYAŞ TÜNELİ AÇILIYOR... Hedef Tarih: {TARGET_DATE}")
    print(f"⚠️  DİKKAT: Sadece {TARGET_DATE} öncesi veriler kullanılacaktır.")

    cnt = 0
    for symbol in symbols:
        try:
            key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path): continue
            
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            def load_and_slice(path):
                if not os.path.exists(path): return pd.DataFrame()
                df = pd.read_parquet(path)
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df = df[~df.index.duplicated(keep='last')]
                df = df.sort_index()
                
                # CRITICAL STEP: Strict Time Slicing
                # We want data strictly BEFORE the Target Date (e.g. up to Jan 27 23:59:59)
                return df[df.index < TARGET_DATE]

            df_1d = load_and_slice(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            if df_1d.empty: continue
            
            # Additional check: Ensure the last data point is recent enough (e.g. closed yesterday)
            # If last data is 5 days ago, data is stale.
            if df_1d.index[-1] < TARGET_DATE - pd.Timedelta(days=2):
                # print(f"DEBUG: {symbol} data stale. Last: {df_1d.index[-1]}")
                continue

            df_4h = load_and_slice(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_and_slice(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_and_slice(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")

            # Calculate EMAs on sliced data
            if not df_1d.empty:
               df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()

            if not df_4h.empty:
                df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            
            if not df_1h.empty:
                for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()
            
            # Get Profile
            dna = get_profile_simple_strict(df_1w, df_1h, df_1d, df_4h)
            
            if dna in golden_dna_list:
                candidates.append({
                    "symbol": symbol,
                    "dna": dna
                })
                cnt += 1
                # print(f"✅ PASSED: {symbol} ({dna})")

        except Exception as e:
            continue

    with open(OUTPUT_FILE, "w") as f:
        json.dump(candidates, f, indent=2)
    
    print(f"🏁 TÜNEL KAPANDI. {cnt} Coin geçiş izni aldı.")
    print(f"📄 Liste kaydedildi: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_tunel()
