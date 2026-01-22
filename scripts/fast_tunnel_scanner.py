import os
import json
import glob
import pandas as pd
import multiprocessing as mp
from datetime import datetime, timedelta

def get_profile_intraday(current_time, df_w, df_d, df_h4, df_h1):
    """
    Ayaş Tüneli v4.1: İntra-day (4S) Prototipi
    Prensip: Günlük veriler 'Çapa' (Anchor) olarak dünkü kapanıştan alınır.
    4S/1S verileri ise 'Canlı' (Live) olarak son kapanmış mumdan alınır.
    """
    try:
        # 1. ÇAPA (ANCHOR): Dünkü Günlük Kapanış Verileri
        anchor_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Faz (Weekly RSI) - Çapa verisi
        sub_w = df_w[df_w.index < anchor_day].tail(30)
        if sub_w.empty: return "neutral"
        
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        # Context (Yearly Retracement) - Çapa verisi
        sub_d_anchor = df_d[df_d.index < anchor_day]
        yr_high = sub_d_anchor.tail(365)['high'].max() if not sub_d_anchor.empty else 1
        retr = (sub_d_anchor.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"

        # 2. CANLI (LIVE): Son Kapanmış Mikro Mumlar
        sub_h1_24 = df_h1[df_h1.index <= current_time].tail(24)
        if sub_h1_24.empty: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        sub_d_last = df_d[df_d.index <= current_time].iloc[-1]
        sub_h4_last = df_h4[df_h4.index <= current_time].iloc[-1]
        sub_h1_last = df_h1[df_h1.index <= current_time].iloc[-1]
        
        s = sum([sub_d_last['close'] > sub_d_last['ema21'], 
                 sub_h4_last['close'] > sub_h4_last['ema21'], 
                 sub_h1_last['close'] > sub_h1_last['ema21']])
        harm = f"harmony_L{s}"
        
        sub_d_tail = df_d[df_d.index <= current_time].tail(10)
        vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_pulse > 2.0 else "active" if vol_pulse > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except:
        return "neutral"

def process_coin(symbol, current_time):
    try:
        def fast_load(tf):
            df = pd.read_parquet(f"coin_cells/{symbol}/data/history_{tf}.parquet")
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df.sort_index(inplace=True)
            df = df[df.index <= current_time].tail(100)
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
            return df

        df_w_raw = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        df_w_raw['dt'] = pd.to_datetime(df_w_raw['timestamp'], unit='ms')
        df_w_raw.set_index('dt', inplace=True)
        
        df_d = fast_load('1d')
        df_h4 = fast_load('4h')
        df_h1 = fast_load('1h')
        
        profile = get_profile_intraday(current_time, df_w_raw, df_d, df_h4, df_h1)
        
        key_path = f"data/golden_keys/{symbol}_key.json"
        with open(key_path, "r") as f:
            allowed = set(json.load(f).get('golden_dna_list', []))
            
        if profile in allowed and profile != "neutral":
            return {'symbol': symbol, 'dna': profile}
    except:
        pass
    return None

def run_fast_scan(target_time_str=None):
    start_all = datetime.now()
    if target_time_str:
        current_time = datetime.strptime(target_time_str, '%Y-%m-%d %H:%M')
    else:
        # Default to now but rounded to last 4H block or similar if needed
        current_time = datetime.now()

    print(f"🚀 FAST TUNNEL SCANNER STARTING... Target: {current_time}")
    
    key_files = glob.glob("data/golden_keys/*_key.json")
    symbols = [os.path.basename(f).split('_')[0] for f in key_files]
    
    cpu_count = mp.cpu_count()
    print(f"💎 Scanning {len(symbols)} coins using {cpu_count} CPU cores...")
    
    with mp.Pool(cpu_count) as pool:
        raw_results = pool.starmap(process_coin, [(s, current_time) for s in symbols])
        
    results = [r for r in raw_results if r]
    
    end_all = datetime.now()
    duration = (end_all - start_all).total_seconds()
    
    print(f"\n✨ SCAN COMPLETED IN {duration:.2f} SECONDS!")
    print(f"🎯 Signals Found: {len(results)}")
    
    if results:
        print("\n--- INTRADAY SIGNALS ---")
        for r in results:
            print(f"| {r['symbol']} | {r['dna']} |")
    else:
        print("\n❌ No signals found in this window.")

if __name__ == "__main__":
    run_fast_scan()
