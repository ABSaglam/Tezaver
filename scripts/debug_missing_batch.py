import pandas as pd
import json
import os

def debug_batch():
    coins = ["METUSDT", "LAZIOUSDT", "REDUSDT", "DUSKUSDT", "RESOLVUSDT"]
    target_date = "2026-01-25" # Source day for Jan 26 Permission
    
    print(f"🕵️‍♂️ Debugging Permission for Target Date: {target_date} (Spawning Jan 26 Access)\n")
    
    for symbol in coins:
        print(f"--- {symbol} ---")
        key_path = f"data/golden_keys/{symbol}_key.json"
        if not os.path.exists(key_path):
            print(f"❌ Key File Missing!")
            continue

        with open(key_path, "r") as f:
            key = json.load(f)
            
        # Load Data
        try:
             df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
             df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
             df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
             df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        except:
            print("❌ Data Load Failed")
            continue

        # Calc Indicators
        for df in [df_w, df_d, df_h4, df_h1]:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df.sort_index(inplace=True)
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

        # PROFILE LOGIC
        day = pd.Timestamp(target_date)
        if day > df_d.index[-1]:
            print(f"❌ Data Ends before target: {df_d.index[-1]}")
            continue
            
        # Context Calc
        sub_d = df_d[df_d.index <= day]
        yr_high_idx = sub_d.tail(365)['high'].idxmax()
        yr_high = sub_d.loc[yr_high_idx]['high']
        close_val = sub_d.iloc[-1]['close']
        retr = (close_val/yr_high - 1)*100
        
        ctx = "mid_zone"
        if retr > -20: ctx = "recovery_high"
        elif retr < -50: ctx = "deep_valley"
        
        print(f"   📊 Retr: {retr:.2f}% (High: {yr_high:.4f} on {yr_high_idx.date()}) -> Ctx: {ctx}")

        # Full Logic for DNA String
        # PHASE
        sub_w = df_w[df_w.index <= day]
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        faz = "neutral"
        if rsi < 40: faz = "derin_dip"
        elif rsi < 60: faz = "birikim_fazi"
        elif rsi < 75: faz = "yukselis_fazi"
        else: faz = "asiri_alim"
        
        # ACC
        sub_h1 = df_h1[df_h1.index <= day].tail(24)
        comp = (sub_h1[['ema9','ema21','ema50']].max(axis=1) / sub_h1[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "loose"
        if min_c < 0.4: acc = "micro_squeeze"
        elif min_c < 0.8: acc = "tight_squeeze"
        elif min_c < 1.5: acc = "coiling"
        
        # HARM
        sub_h4 = df_h4[df_h4.index <= day]
        s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
                 sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
                 sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
        harm = f"harmony_L{s}"
        
        # RHY
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
        ritim = "active" if vol_pulse > 1.0 else "sleeping"
        if vol_pulse > 2.0: ritim = "ignited"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        dna = f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
        
        if dna in key['golden_dna_list']:
            print(f"   ✅ MATCH! DNA: {dna}")
        else:
            print(f"   ❌ NO MATCH. DNA: {dna}")
            # Try to find partial match
            print("   (Reason: likely context or phase shift)")

if __name__ == "__main__":
    debug_batch()
