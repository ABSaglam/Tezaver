import pandas as pd
import numpy as np
import json
import os

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "KITEUSDT"
TARGET_DATE = pd.Timestamp("2026-01-28")

def get_profile_simple(day, df_w, df_h1, df_d, df_h4, strict_before=True):
    try:
        daily_integrity_cutoff = day.normalize()
        cutoff_w = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index <= cutoff_w].tail(30)
        
        if len(sub_w) < 15: return f"neutral (week_len={len(sub_w)})"
        
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        if np.isnan(rsi_val): return "neutral (nan_rsi)"
        
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        if strict_before:
            sub_h1_24 = df_h1[df_h1.index < day].tail(24)
            sub_d = df_d[df_d.index < daily_integrity_cutoff]
            sub_h4 = df_h4[df_h4.index < day]
            sub_h1 = df_h1[df_h1.index < day]
        
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral (no_h1_24)"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral (empty_sub)"
        if sub_d.iloc[-1].isnull().any(): return "neutral (null_daily)"

        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + \
            int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + \
            int(sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_p = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except Exception as e: return f"neutral ({e})"

def check_kite():
    print(f"Checking {SYMBOL} for {TARGET_DATE}...")
    
    key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{SYMBOL}_key.json"
    with open(key_path, "r") as f:
        golden_dna_list = set(json.load(f).get('golden_dna_list', []))
    
    def load_clean(path):
        df = pd.read_parquet(path)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df = df[~df.index.duplicated(keep='last')]
        return df.sort_index()

    df_1d = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_1d.parquet")
    df_4h = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_4h.parquet")
    df_1h = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_1h.parquet")
    df_1w = load_clean(f"{COIN_CELLS_DIR}/{SYMBOL}/data/history_1w.parquet")
    
    df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
    for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()

    # CHECK AYAŞ
    dna_ayas = get_profile_simple(TARGET_DATE, df_1w, df_1h, df_1d, df_4h, strict_before=True)
    is_golden = dna_ayas in golden_dna_list
    
    print(f"Calculated DNA: {dna_ayas}")
    print(f"Is Golden? {is_golden}")
    
    if not is_golden:
        print("Golden DNA List Sample:")
        for d in list(golden_dna_list)[:5]:
            print(f" - {d}")

if __name__ == "__main__":
    check_kite()
