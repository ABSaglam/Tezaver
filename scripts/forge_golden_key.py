import json
import pandas as pd
import sys
import os
from tezaver.core.rally_store import RallyStore

# AYAŞ TÜNELİ v4 (PURE PREDICTION) - GOLDEN KEY GENERATOR
# This script runs the pipeline and saves the "Golden Key" (Genetic Template)

def forge_golden_key(symbol):
    print(f"\n⚒️ FORGING GOLDEN KEY (v4) FOR: {symbol}")
    
    # 0. Check Data Existence
    required_files = ['history_1w.parquet', 'history_1d.parquet', 'history_4h.parquet', 'history_1h.parquet']
    for f in required_files:
        if not os.path.exists(f"coin_cells/{symbol}/data/{f}"):
            print(f"❌ Missing data for {symbol}: {f}")
            return

    # 1. Generate & Save Profiles (Fresh)
    # We do this inline to avoid dependency on old files
    try:
        df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
        df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
        df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
    except Exception as e:
        print(f"❌ Read Error: {e}")
        return

    # -- Profile Logic (Same as v3/v4 standard) --
    for df in [df_w, df_d, df_h4, df_h1]:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
    def get_profile(day):
        # ... (Identical logic to v4 pipeline to ensure consistency)
        # Re-implementing simplified for the single-file runner
        # PHASE
        sub_w = df_w[df_w.index <= day]
        if sub_w.empty: return "neutral"
        # Quick Calc RSI
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
        s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
                 sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
                 sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
        harm = f"harmony_L{s}"
        
        # RHYTHM & ENERGY
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
        ritim = "active" if vol_pulse > 1.0 else "sleeping"
        if vol_pulse > 2.0: ritim = "ignited"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        # CONTEXT
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "mid_zone"
        if retr > -20: ctx = "recovery_high"
        elif retr < -50: ctx = "deep_valley"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

    print("   -> Extracting DNA Profiles...")
    profiles = {date.strftime('%Y-%m-%d'): get_profile(date) for date in df_d.index}
    
    # 2. Match with Rallies (T+1 Strict)
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}
    
    # 3. Evolution (Find the Golden Key)
    candidates = {} # Family -> Hit Count
    
    for date_str, dna in profiles.items():
        if dna not in candidates: candidates[dna] = {'hits': 0, 'fails': 0}
        
        curr_date = pd.Timestamp(date_str)
        target_date = curr_date + pd.Timedelta(days=1)
        
        if target_date in rally_days:
            candidates[dna]['hits'] += 1
        elif curr_date in rally_days:
            # T=0 Leak (disqualified)
            candidates[dna]['fails'] += 1
        else:
            # T+1 Miss (False Positive)
            candidates[dna]['fails'] += 1
            
    # Filter 100% Purity
    golden_families = [dna for dna, stats in candidates.items() if stats['hits'] > 0 and stats['fails'] == 0]
    
    if not golden_families:
        print("⚠️ No 100% Pure Families found for this coin.")
        return

    # 4. Save Final Asset Package
    total_hits = sum(candidates[dna]['hits'] for dna in golden_families)
    
    golden_key_data = {
        'symbol': symbol,
        'protocol': 'v4_pure_prediction',
        'total_signals': total_hits,
        'unique_dna_count': len(golden_families),
        'golden_dna_list': golden_families
    }
    
    key_path = f"data/golden_keys/{symbol}_key.json"
    with open(key_path, "w") as f:
        json.dump(golden_key_data, f, indent=2)
        
    print(f"🏆 GOLDEN KEY FORGED: {symbol}")
    print(f"   -> Saved to: {key_path}")
    print(f"   -> Pure Signals: {total_hits}")
    print(f"   -> Valid DNA Strands: {len(golden_families)}")

if __name__ == "__main__":
    forge_golden_key(sys.argv[1])
