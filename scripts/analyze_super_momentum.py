
import sys
import pandas as pd
import numpy as np
from pathlib import Path
# from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path.cwd() / "src"))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

def compute_rsi(data, window=14):
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=window - 1, adjust=False).mean()
    ema_down = down.ewm(com=window - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def analyze_super_momentum():
    print("=== Super Momentum Analyzer (15m) ===")
    print("Conditions:")
    print("1. Vol > 5x SMA50 (Trigger)")
    print("2. RSI > 70 (Trigger)")
    print("3. Next Bar: RSI > Prev RSI AND Volume > 2x SMA50 (Sustained)")
    
    results = []
    
    print(f"Scanning {len(DEFAULT_COINS)} coins...")
    for i, symbol in enumerate(DEFAULT_COINS):
        if i % 50 == 0: print(f"Processing {i}/{len(DEFAULT_COINS)}...")
        try:
            # Load raw history
            hist_path = coin_cell_paths.get_history_file(symbol, "15m")
            if not hist_path.exists():
                continue
                
            df = pd.read_parquet(hist_path)
            if df.empty or len(df) < 200:
                continue
                
            # Compute Indicators
            df['rsi'] = compute_rsi(df['close'], 14)
            df['rsi_ema'] = df['rsi'].ewm(span=9).mean()
            df['vol_sma50'] = df['volume'].rolling(50).mean()
            
            # Compute ATR
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = tr.rolling(14).mean()
            df['atr_pct'] = df['atr'] / df['close']

            # Shift for previous values
            df['prev_rsi'] = df['rsi'].shift(1)
            df['prev_rsi_ema'] = df['rsi_ema'].shift(1)
            df['prev_vol'] = df['volume'].shift(1)
            
            # --- Logic ---
            # Condition 1 (Trigger Bar T-1)
            # Actually, let's look at current bar T as the "Follow Through" bar
            # So T-1 must be the Trigger.
            
            # Trigger Criteria at T-1:
            # Vol(T-1) > 5 * SMA50(T-1)
            # RSI(T-1) > 70
            
            c1_trigger_vol = df['prev_vol'] > (5 * df['vol_sma50'].shift(1))
            c1_trigger_rsi = df['prev_rsi'] > 70
            
            # Condition 2 (Follow Through Bar T)
            # RSI(T) > RSI(T-1)
            # RSI_EMA(T) > RSI_EMA(T-1)
            # Vol(T) > 2 * SMA50(T) (Interpretation of "Sustained Volume")
            
            # RELAXED MODE:
            # Vol(T) > 2 * SMA50(T) (Instead of previous volume)
            c2_follow_vol = df['volume'] > (2 * df['vol_sma50']) 
            
            # RSI Rising
            c2_follow_rsi = (df['rsi'] > df['prev_rsi']) & (df['rsi_ema'] > df['prev_rsi_ema'])
            
            # Condition 3: Volatility (The "Wild Candle" Rule)
            # ATR% > 2.0% (0.02)
            c3_volatility = df['atr_pct'] > 0.02
            
            # Combined Mask
            mask = c1_trigger_vol & c1_trigger_rsi & c2_follow_vol & c2_follow_rsi & c3_volatility
            
            events = df[mask].copy()
            # if not events.empty:
            #    print(f"[{symbol}] HIT Found!")
            
            for idx, row in events.iterrows():
                # Analyze Outcome
                # Get next 96 bars (24h)
                start_loc = df.index.get_loc(idx)
                if start_loc + 96 >= len(df):
                    continue
                    
                future = df.iloc[start_loc+1 : start_loc+97]
                
                # short term future (6 bars = 1.5h)
                future_6 = df.iloc[start_loc+1 : start_loc+7] 
                
                entry_price = row['close']
                
                # 24h Metrics
                max_price = future['high'].max()
                min_price = future['low'].min()
                exit_price = future['close'].iloc[-1]
                
                # 6-Bar Metrics
                if not future_6.empty:
                    fast_max = future_6['high'].max()
                    fast_min = future_6['low'].min()
                    fast_gain = (fast_max - entry_price) / entry_price
                    fast_draw = (fast_min - entry_price) / entry_price
                else:
                    fast_gain = 0
                    fast_draw = 0
                
                max_gain = (max_price - entry_price) / entry_price
                max_drawdown = (min_price - entry_price) / entry_price
                final_return = (exit_price - entry_price) / entry_price
                
                date_val = row.get('open_time')
                if date_val is None:
                    date_val = row.get('date')
                if date_val is None:
                    date_val = row.get('timestamp')
                if date_val is None:
                    # Fallback to index if datetime
                    date_val = idx

                results.append({
                    'symbol': symbol,
                    'date': date_val, # Assuming compatible col
                    'entry_price': entry_price,
                    'trigger_vol_factor': row['prev_vol'] / row['vol_sma50'], # Approx
                    'follow_vol_factor': row['volume'] / row['vol_sma50'], # Changed to SMA for consistency
                    'rsi_val': row['rsi'],
                    'rsi_growth': row['rsi'] - row['prev_rsi'],
                    'atr_pct': row['atr_pct'],
                    'max_gain_24h': max_gain,
                    'max_drawdown_24h': max_drawdown,
                    'final_return_24h': final_return,
                    'fast_gain_6bar': fast_gain,
                    'fast_draw_6bar': fast_draw
                })
                
        except Exception as e:
            # print(f"[{symbol}] Error: {e}")
            continue
            
    # Report
    if not results:
        print("No events found matching stricter criteria.")
        return
        
    res_df = pd.DataFrame(results)
    
    # --- Tier Classification ---
    def assign_tier(gain):
        if gain >= 0.30: return "DIAMOND"
        elif gain >= 0.20: return "GOLD"
        elif gain >= 0.10: return "SILVER"
        elif gain >= 0.05: return "BRONZE"
        else: return "IRON"
        
    res_df['tier'] = res_df['max_gain_24h'].apply(assign_tier)
    
    print(f"\nFound {len(res_df)} events.")
    print("\n=== DIAMOND vs GOLD vs TRAPS (Feature Analysis) ===")
    
    comp_tiers = ['DIAMOND', 'GOLD', 'IRON']
    
    header = f"{'FEATURE':<20} | {'DIAMOND':<10} | {'GOLD':<10} | {'IRON (Trap)':<12}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    # Features to compare (Mean)
    features = {
        'Vol Factor (Follow)': 'follow_vol_factor',
        'RSI Value': 'rsi_val',
        'RSI Growth': 'rsi_growth',
        'Volatility (ATR%)': 'atr_pct'
    }
    
    for label, col in features.items():
        vals = []
        for tier in comp_tiers:
            mean_val = res_df[res_df['tier'] == tier][col].mean()
            if col == 'atr_pct': mean_val *= 100 # Show as %
            vals.append(f"{mean_val:.2f}")
            
        print(f"{label:<20} | {vals[0]:<10} | {vals[1]:<10} | {vals[2]:<12}")

    print("-" * len(header))
    
    # --- Performance Table ---
    print("\n=== FINAL STRATEGY PERFORMANCE (ATR > 2%) ===")
    
    header_perf = f"{'TIER':<10} | {'COUNT':<6} | {'AVG GAIN':<10} | {'AVG DRAW':<10} | {'FINAL RET':<10} | {'WIN RATE':<8}"
    print("-" * len(header_perf))
    print(header_perf)
    print("-" * len(header_perf))
    
    tiers = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON']
    for tier in tiers:
        tdf = res_df[res_df['tier'] == tier]
        count = len(tdf)
        if count == 0:
            continue
            
        avg_gain = tdf['max_gain_24h'].mean() * 100
        avg_draw = tdf['max_drawdown_24h'].mean() * 100
        avg_final = tdf['final_return_24h'].mean() * 100
        win_rate = (len(tdf[tdf['max_gain_24h'] > 0.02]) / count) * 100
        
        print(f"{tier:<10} | {count:<6} | {avg_gain:>9.2f}% | {avg_draw:>9.2f}% | {avg_final:>9.2f}% | {win_rate:>7.1f}%")

    print("-" * len(header_perf))
    
    # Overall Stats
    print("\n--- OVERALL STATS ---")
    ov_avg_gain = res_df['max_gain_24h'].mean() * 100
    ov_win_rate = (len(res_df[res_df['max_gain_24h'] > 0.02]) / len(res_df)) * 100
    print(f"Total Events: {len(res_df)}")
    print(f"Overall Win Rate: {ov_win_rate:.1f}%")
    print(f"Overall Avg Gain: {ov_avg_gain:.2f}%")
    
    # --- CONDITIONAL PROBABILITY (The "Silver Breakout" Test) ---
    print("\n=== SILVER BREAKOUT ANALYSIS (+5% Rule) ===")
    
    # Filter: Events that reached at least +5%
    breakout_df = res_df[res_df['max_gain_24h'] >= 0.05]
    total_breakouts = len(breakout_df)
    
    if total_breakouts > 0:
        hit_10 = len(breakout_df[breakout_df['max_gain_24h'] >= 0.10])
        hit_20 = len(breakout_df[breakout_df['max_gain_24h'] >= 0.20])
        hit_30 = len(breakout_df[breakout_df['max_gain_24h'] >= 0.30])
        
        avg_peak = breakout_df['max_gain_24h'].mean() * 100
        
        print(f"Total Events Reaching +5%: {total_breakouts}")
        print(f"Avg Peak after +5%: +{avg_peak:.2f}%")
        print(f"Probability of hitting +10%: {(hit_10/total_breakouts)*100:.1f}%")
        print(f"Probability of hitting +20%: {(hit_20/total_breakouts)*100:.1f}%")
        print(f"Probability of hitting +30% (Diamond): {(hit_30/total_breakouts)*100:.1f}%")
    else:
        print("No events reached +5%.")

    # --- ROCKET ANALYSIS (Straight Up, No Wick) ---
    print("\n=== ROCKET ANALYSIS (Direct to Moon in <6 Bars) ===")
    
    # Filter: 
    # 1. Gain > 5% within 6 bars.
    # 2. Drawdown > -1.5% (Tiny risk).
    
    rocket_df = res_df[
        (res_df['fast_gain_6bar'] >= 0.05) & 
        (res_df['fast_draw_6bar'] >= -0.015)
    ]
    
    count_rockets = len(rocket_df)
    total_events = len(res_df)
    
    if count_rockets > 0:
        avg_rocket_gain = rocket_df['max_gain_24h'].mean() * 100
        avg_rocket_final = rocket_df['final_return_24h'].mean() * 100
        
        hit_10 = len(rocket_df[rocket_df['max_gain_24h'] >= 0.10])
        hit_20 = len(rocket_df[rocket_df['max_gain_24h'] >= 0.20])
        hit_30 = len(rocket_df[rocket_df['max_gain_24h'] >= 0.30])
        
        print(f"Total Rockets Found: {count_rockets} ({(count_rockets/total_events)*100:.1f}% of signals)")
        print(f"Avg Rocket Peak (24h): +{avg_rocket_gain:.2f}%")
        print(f"Avg Rocket Final (24h): +{avg_rocket_final:.2f}%")
        print(f"Prob of +10%: {(hit_10/count_rockets)*100:.1f}%")
        print(f"Prob of +20%: {(hit_20/count_rockets)*100:.1f}%")
        
        # Rocket Features Comparison
        print("\n--- ROCKET FEATURES (What makes them fly?) ---")
        print(f"Rocket Vol Factor: {rocket_df['follow_vol_factor'].mean():.2f}")
        print(f"Rocket RSI Value: {rocket_df['rsi_val'].mean():.2f}")
        print(f"Rocket RSI Growth: {rocket_df['rsi_growth'].mean():.2f}")
        print(f"Rocket ATR%: {rocket_df['atr_pct'].mean()*100:.2f}%")
        
    else:
        print("No ROCKET events found (Gain>5%, Draw<-1.5% in 6 bars).")

if __name__ == "__main__":
    analyze_super_momentum()
