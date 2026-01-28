import pandas as pd
import numpy as np
from datetime import timedelta
from tezaver.core.rally_store import RallyStore
import json

# CONFIG
SYMBOL = "DASHUSDT"
TRAINING_END_DATE = pd.Timestamp("2025-09-30") # SON 3 AY ve OCAK 2026 HARİÇ

def analyze_flash_raid_fingerprint():
    print(f"🦅 FLASH-RAID ANALYZER: {SYMBOL}")
    print(f"🔒 Training Limit: {TRAINING_END_DATE}")
    
    # 1. Load Data
    try:
        df_15m = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_15m.parquet")
        df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('dt', inplace=True)
        df_15m.sort_index(inplace=True)
        
        # Calculate Base Indicators
        df_15m['rsi'] = 100 - (100 / (1 + df_15m['close'].diff().where(lambda x: x>0, 0).rolling(14).mean() / (-df_15m['close'].diff().where(lambda x: x<0, 0).rolling(14).mean()).replace(0, 0.001)))
        
        # Volume Spike Ratio (vs previous 20 candles mean)
        df_15m['vol_mean_20'] = df_15m['volume'].rolling(20).mean().shift(1)
        df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_mean_20'].replace(0, 1)
        
        # Body Size %
        df_15m['body_pct'] = (df_15m['close'] / df_15m['open'] - 1) * 100
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    # 2. Get Historical Rallies (Only Training Data)
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=SYMBOL, timeframe='15m')
    
    training_rallies = []
    for r in all_rallies:
        r_time = pd.Timestamp(r['event_time'])
        if r_time > TRAINING_END_DATE: continue # SKIP RECENT DATA
        
        # Only Diamond and Gold (Strong Rallies)
        if r.get('tier') not in ['DIAMOND', 'GOLD']: continue
        
        training_rallies.append(r)
        
    print(f"📚 Analysis Set: {len(training_rallies)} High-Quality Rallies (Pre-Oct 2025)")
    
    # 3. Analyze The "Spark" Candle (The candle BEFORE the rally triggers or AT trigger)
    # Usually RallyStore event_time is the trigger time. Let's look at that specific 15m candle.
    
    spark_stats = {
        'vol_ratios': [],
        'rsis': [],
        'body_pcts': []
    }
    
    for r in training_rallies:
        trigger_time = pd.Timestamp(r['event_time'])
        
        # Find the 15m candle at trigger time
        if trigger_time not in df_15m.index:
            # Try finding the closest previous one if exact match fails
            loc_idx = df_15m.index.get_indexer([trigger_time], method='pad')[0]
            if loc_idx == -1: continue
            candle = df_15m.iloc[loc_idx]
        else:
            candle = df_15m.loc[trigger_time]
            
        spark_stats['vol_ratios'].append(candle['vol_ratio'])
        spark_stats['rsis'].append(candle['rsi'])
        spark_stats['body_pcts'].append(candle['body_pct'])
        
    # 4. Generate Fingerprint (The "ACA ELITE Identity")
    if not spark_stats['vol_ratios']:
        print("❌ No valid spark data found.")
        return

    print("\n🧬 ACAUSDT ELITE FLASH-RAID FINGERPRINT (First 15m Candle):")
    
    # STRICTER CRITERIA: Target the top 25% of rallies (75th percentile)
    # We want the "Obvious" breakouts, not the subtle ones.
    
    min_vol = np.percentile(spark_stats['vol_ratios'], 50) # Median (Stronger than 25th)
    avg_vol = np.mean(spark_stats['vol_ratios'])
    
    # RSI: Must be already hot or heating up
    min_rsi = 55.0 # Fixed minimum to avoid very low momentum starts
    max_rsi = 90.0
    
    # Body: Must be a solid green candle
    min_body = 0.5 # At least 0.5% gain in 15m candle
    
    print(f"   🔹 Volume Burst: > {min_vol:.2f}x (Avg: {avg_vol:.2f}x)")
    print(f"   🔹 RSI Range: {min_rsi:.1f}+")
    print(f"   🔹 Price Thrust: > %{min_body:.2f}")
    
    fingerprint = {
        'min_vol_ratio': float(min_vol),
        'min_rsi': float(min_rsi),
        'min_body_pct': float(min_body)
    }
    
    # 5. BLIND TEST WITH TUNNEL INTELLIGENCE (Golden Key + Flash Raid)
    print("\n🧪 BLIND TEST: TUNNEL + ELITE SNIPER (Güç Birliği)")
    print("   Scanning Oct 2025 - Jan 2026...")
    
    # Load Golden Key
    with open(f"data/golden_keys/{SYMBOL}_key.json", "r") as f:
        golden_dna_list = set(json.load(f).get('golden_dna_list', []))
        
    # Load Macro Data for Profile Calculation
    df_w = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1w.parquet")
    df_w['dt'] = pd.to_datetime(df_w['timestamp'], unit='ms')
    df_w.set_index('dt', inplace=True)
    
    df_d = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1d.parquet")
    df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
    df_d.set_index('dt', inplace=True)
    df_d['ema21'] = df_d['close'].ewm(span=21, adjust=False).mean() # Needed for profile
    
    df_h4 = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_4h.parquet")
    df_h4['dt'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
    df_h4.set_index('dt', inplace=True)
    df_h4['ema21'] = df_h4['close'].ewm(span=21, adjust=False).mean()
    
    # Need H1 for profile too
    df_h1 = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_1h.parquet")
    df_h1['dt'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('dt', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    # Helper for Profile (Copied from audit scripts for consistency)
    def get_profile_simple(day):
        # Simplified version or reuse the robust one if imported
        # For speed in this test, we assume the helper function exists or re-implement minimal
        try:
            # Re-implementing minimal profile logic to be self-contained in this test script
            sub_w = df_w[df_w.index <= day].tail(30)
            if sub_w.empty: return "neutral"
            delta = sub_w['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
            rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
            
            sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
            if sub_h1_24.empty: return "neutral"
            comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
            min_c = comp.min()
            acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
            
            sub_d = df_d[df_d.index <= day]
            sub_h4 = df_h4[df_h4.index <= day]
            sub_h1_sub = df_h1[df_h1.index <= day]
            if sub_d.empty or sub_h4.empty or sub_h1_sub.empty: return "neutral"
            
            s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
            harm = f"harmony_L{s}"
            
            sub_d_tail = sub_d.tail(10)
            vol_pulse = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
            ritim = "ignited" if vol_pulse > 2.0 else "active" if vol_pulse > 1.0 else "sleeping"
            
            v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
            enerji = "building_energy" if v_trend else "depleting_energy"
            
            yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
            retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
            ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
            
            return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
        except: return "neutral"

    test_df = df_15m[df_15m.index > TRAINING_END_DATE].copy()
    matches = []
    
    # Cache for daily profiles to speed up
    daily_profiles = {}
    
    for idx, row in test_df.iterrows():
        current_day = idx.normalize()
        
        # 1. TUNNEL CHECK (Permission)
        if current_day not in daily_profiles:
            # We calculate profile based on YESTERDAY's close (T-1) as tunnel does
            profile_day = current_day # In v4 we use current_day because we run at 00:00 or after
            # Wait, get_profile uses <= day. If we run at 10:00 AM, we should probably use data up to 00:00?
            # v4 Standard: "Prediction at 00:00 for the day". So we use data up to 00:00.
            # Ideally passing the exact timestamp.
            # Let's say we check profile at the start of the day.
            daily_profiles[current_day] = get_profile_simple(current_day)
            
        dna = daily_profiles[current_day]
        if dna not in golden_dna_list: 
            continue # TUNNEL DENIED PERMISSION!
            
        # 2. SNIPER CHECK (Execution)
        if (row['vol_ratio'] >= fingerprint['min_vol_ratio'] and 
            row['rsi'] >= fingerprint['min_rsi'] and
            row['body_pct'] >= fingerprint['min_body_pct']):
            
            # Check result (Next 12 candles / 3 hours)
            future = test_df.loc[test_df.index > idx].head(12)
            if future.empty: continue
            
            entry_price = row['close']
            max_price = future['high'].max()
            max_gain = (max_price / entry_price - 1) * 100
            min_loss = (future['low'].min() / entry_price - 1) * 100
            
            # --- PROFIT CAPTURE ANALYSIS ---
            # Did we enter early? 
            # Look at the whole day's range to see where our entry sits
            day_data = df_15m[df_15m.index.normalize() == current_day]
            day_low = day_data['low'].min()
            day_high = day_data['high'].max()
            day_range = day_high - day_low
            if day_range == 0: day_range = 1
            entry_pos = (entry_price - day_low) / day_range # 0.0 = Bottom, 1.0 = Top
            
            # Simulation: Simple Trailing Stop (Run until candle closes below EMA9)
            # Find exit candle
            exit_price = entry_price
            exit_time = idx
            held_candles = 0
            
            # Use future candles (up to end of day)
            trade_future = test_df.loc[test_df.index > idx]
            
            for f_idx, f_row in trade_future.iterrows():
                # Exit Condition 1: Time Stop (12 candles / 3 hours)
                if held_candles >= 12: 
                    exit_price = f_row['close']
                    exit_time = f_idx
                    break
                
                # Exit Condition 2: Trailing Logic (Close < 9 EMA - rough approx)
                # Since we don't have EMA9 in test_df readily calculated for every step, 
                # let's use a simpler heuristic: Close < Previous Low
                prev_low = test_df.shift(1).loc[f_idx]['low']
                if f_row['close'] < prev_low:
                     exit_price = f_row['close']
                     exit_time = f_idx
                     break
                
                max_in_trade = (f_row['high'] / entry_price - 1) * 100
                if max_in_trade > 15: # Moonbag secure
                     # If we hit huge profit, maybe take it? 
                     pass 
                
                held_candles += 1
                
            realized_gain = (exit_price / entry_price - 1) * 100

            matches.append({
                'time': idx,
                'vol': row['vol_ratio'],
                'entry_price': entry_price,
                'max_pot_gain': max_gain,
                'realized_gain': realized_gain,
                'capture_efficiency': (realized_gain / max_gain * 100) if max_gain > 0 else 0,
                'entry_quality': (1 - entry_pos) * 100, # Higher is better (closer to bottom)
                'duration': held_candles * 15
            })
            
    print(f"   🎯 Total Signals Found: {len(matches)}")
    
    # Analyze Results
    wins = [m for m in matches if m['realized_gain'] >= 1.0] # 1% Realized is a win
    big_wins = [m for m in matches if m['realized_gain'] >= 5.0]
    
    if matches:
        win_rate = len(wins) / len(matches) * 100
        avg_realized = np.mean([m['realized_gain'] for m in matches])
        avg_potential = np.mean([m['max_pot_gain'] for m in matches])
        avg_quality = np.mean([m['entry_quality'] for m in matches])
        
        print(f"\n🏆 TRADE SIMULATION RESULTS (Realized):")
        print(f"   Win Rate (>1% Net): %{win_rate:.1f}")
        print(f"   Avg Realized Gain: %{avg_realized:.2f} (vs Max Potential: %{avg_potential:.2f})")
        print(f"   Avg Entry Quality: {avg_quality:.0f}/100 (100 = Exact Bottom)")
        print(f"   Avg Duration: {np.mean([m['duration'] for m in matches]):.0f} min")
        
        print("\n   Top 5 Best Trades:")
        matches.sort(key=lambda x: x['realized_gain'], reverse=True)
        for m in matches[:5]:
            print(f"   🌟 {m['time']} | Ent: {m['entry_quality']:.0f}/100 | Pot: %{m['max_pot_gain']:.1f} -> NET: %{m['realized_gain']:.2f} ({m['duration']}m)")
            
        print("\n   Last 5 Trades:")
        matches.sort(key=lambda x: x['time'])
        for m in matches[-5:]:
             res = "✅" if m['realized_gain'] > 0 else "🔻"
             print(f"   {res} {m['time']} | Pot: %{m['max_pot_gain']:.1f} -> NET: %{m['realized_gain']:.2f}")

if __name__ == "__main__":
    analyze_flash_raid_fingerprint()
