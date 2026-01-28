import pandas as pd
import json
import os

def debug_resolv():
    symbol = "RESOLVUSDT"
    
    # 1. Load Key
    with open(f"data/golden_keys/{symbol}_key.json", "r") as f:
        key = json.load(f)
    print("🔑 Golden Key Allowed DNAs:")
    for d in key['golden_dna_list']:
        print(f"   - {d}")
        
    # 2. Calc DNA for Jan 26 (Source Day: Jan 25)
    # Re-using the exact logic from verify script
    
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

    def get_profile(day):
        day = pd.Timestamp(day)
        
        # PHASE
        sub_w = df_w[df_w.index <= day]
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        faz = "neutral"
        if rsi < 40: faz = "derin_dip"
        elif rsi < 60: faz = "birikim_fazi"
        elif rsi < 75: faz = "yukselis_fazi"
        else: faz = "asiri_alim"
        
        # ACCUMULATION (H1)
        sub_h1 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1.empty: return "neutral"
        comp = (sub_h1[['ema9','ema21','ema50']].max(axis=1) / sub_h1[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "loose"
        if min_c < 0.4: acc = "micro_squeeze"
        elif min_c < 0.8: acc = "tight_squeeze"
        elif min_c < 1.5: acc = "coiling"
        
        # HARMONY
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        if sub_d.empty or sub_h4.empty: return "neutral"
        
        # FIX: Check if we have data FOR that day.
        # Use tail(1) of the subset
        d_row = sub_d.iloc[-1]
        h4_row = sub_h4.iloc[-1]
        h1_row = sub_h1.iloc[-1]
        
        s = sum([d_row['close']>d_row['ema21'], 
                 h4_row['close']>h4_row['ema21'], 
                 h1_row['close']>h1_row['ema21']])
        harm = f"harmony_L{s}"
        
        # RHYTHM
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
        ritim = "active" if vol_pulse > 1.0 else "sleeping"
        if vol_pulse > 2.0: ritim = "ignited"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high_idx = sub_d.tail(365)['high'].idxmax() if len(sub_d)>0 else day
        yr_high = sub_d.loc[yr_high_idx]['high'] if len(sub_d)>0 else 1
        
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        print(f"   [DEBUG] Date: {day.date()} | Close: {sub_d.iloc[-1]['close']:.4f}")
        print(f"   [DEBUG] YrHigh: {yr_high:.4f} on {yr_high_idx.date()} | Retr: {retr:.2f}%")
        
        ctx = "mid_zone"
        if retr > -20: ctx = "recovery_high"
        elif retr < -50: ctx = "deep_valley"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

    # Check Jan 25 (Source for Jan 26)
    target_date = "2026-01-25"
    
    print(f"   [DEBUG] Data Start Date: {df_d.index[0]}")
    print(f"   [DEBUG] Data End Date:   {df_d.index[-1]}")
    
    dna = get_profile(target_date)
    print(f"\n🧬 Calculated DNA for {target_date}:")
    print(f"   {dna}")
    
    if dna in key['golden_dna_list']:
        print("✅ MATCH! (Permission GRANTED)")
    else:
        print("❌ NO MATCH! (Permission DENIED)")

if __name__ == "__main__":
    debug_resolv()
