
import pandas as pd
import numpy as np
import tezaver.core.coin_cell_paths as coin_cell_paths
from tezaver.core import config
# from tqdm import tqdm

def analyze_rocket_continuation():
    print("=== ROCKET CONTINUATION ANALYZER ===")
    print("Focus: If we miss the start (Bar 0), can we enter at Bar 1 or 2?")
    print("Target Population: Pure 30% Rockets (Gain > 30% in 11 bars)")
    
    coins = config.DEFAULT_COINS
    
    stats = []
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0: print(f"Scanning {i}/{len(coins)}...", end='\r')
        
        p = coin_cell_paths.get_history_file(symbol, "15m")
        if not p.exists(): continue
        df = pd.read_parquet(p)
        if df.empty or len(df) < 300: continue
        
        # Features
        df['vol_sma50'] = df['volume'].rolling(50).mean()
        df['vol_factor'] = df['volume'] / df['vol_sma50']
        
        delta = df['close'].diff()
        up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
        rs = up.ewm(com=13, adjust=False).mean() / down.ewm(com=13, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Candle Size
        df['body_pct'] = (df['close'] - df['open']) / df['open']
        df['high_pct'] = (df['high'] - df['open']) / df['open']
        
        # FUTURE LOOKAHEAD
        # We need to find the "Start" of a 30% rally.
        # How do we define start? The bar from which the next 11 bars go +30%.
        # (Same definition as before)
        
        rev_high = df['high'].iloc[::-1]
        future_max = rev_high.rolling(11).max().iloc[::-1].shift(-1)
        df['future_gain'] = (future_max - df['close']) / df['close']
        
        # Identify Rockets
        # Filter: Gain > 30%
        # AND ensure we capture unique events (not just 11 consecutive bars of the same rally).
        # We'll simple iterate and skip overlapped.
        
        is_rocket = df['future_gain'] >= 0.30
        idxs = np.where(is_rocket)[0]
        
        last_idx = -999
        
        for idx in idxs:
            if idx < last_idx + 15: continue # Skip overlap to find unique rally starts
            
            # This 'idx' is Bar 0 (T=0).
            # We assume user missed this.
            
            if idx + 12 >= len(df): continue
            
            # Bar 0 Stats
            row0 = df.iloc[idx]
            
            # Bar 1 (T+1)
            row1 = df.iloc[idx+1]
            
            # Bar 2 (T+2)
            row2 = df.iloc[idx+2]
            
            # Remaining Potential from Bar 1 Close
            # Future max from T+1 to T+11 is roughly same peak
            peak_price = df.iloc[idx+1:idx+12]['high'].max()
            rem_gain_1 = (peak_price - row1['close']) / row1['close']
            
            # Drawdown from Bar 1 Close (Risk)
            # Find min low before peak? Or just min low in next few bars?
            # Let's say risk to stop loss.
            min_price = df.iloc[idx+1:idx+12]['low'].min()
            draw_1 = (min_price - row1['close']) / row1['close']

            # Metrics
            stats.append({
                'symbol': symbol,
                'bar0_gain': row0['body_pct'],
                'bar0_vol': row0['vol_factor'],
                'bar0_rsi': row0['rsi'],
                
                'bar1_gain': row1['body_pct'], # Did it continue?
                'bar1_vol': row1['vol_factor'],
                'bar1_color': 'GREEN' if row1['close'] > row1['open'] else 'RED',
                
                'rem_gain_1': rem_gain_1, # Profit left after T+1
                'draw_1': draw_1,
                
                'bar2_gain': row2['body_pct'],
                'rem_gain_2': (peak_price - row2['close']) / row2['close']
            })
            
            last_idx = idx

    print("\n\n=== CONTINUATION ANALYSIS RESULTS ===")
    res = pd.DataFrame(stats)
    count = len(res)
    print(f"Unique Rockets Analyzed: {count}")
    
    if count == 0: return

    # 1. Bar 0 Anatomy (The One We Missed)
    print("\n--- BAR 0 (The Start) ---")
    print(f"Avg Gain: {res['bar0_gain'].mean()*100:.2f}%")
    print(f"Avg Volume: {res['bar0_vol'].mean():.2f}x")
    print(f"Avg RSI: {res['bar0_rsi'].mean():.2f}")
    
    # 2. Bar 1 Anatomy (The Opportunity?)
    print("\n--- BAR 1 (Next 15 mins) ---")
    print(f"Avg Gain: {res['bar1_gain'].mean()*100:.2f}%")
    print(f"Green Candles: {len(res[res['bar1_gain']>0])} ({len(res[res['bar1_gain']>0])/count*100:.1f}%)")
    print(f"Avg Vol: {res['bar1_vol'].mean():.2f}x")
    
    # 3. Late Entry Performance (Enter at Close of Bar 1)
    print("\n--- LATE ENTRY PERFORMANCE (Enter at Close of Bar 1) ---")
    print(f"Avg Remaining Gain: {res['rem_gain_1'].mean()*100:.2f}%")
    
    # Win Rate: Can we catch +10% from here?
    wins = len(res[res['rem_gain_1'] >= 0.10])
    print(f"Prob of catching +10% MORE: {wins} ({wins/count*100:.1f}%)")
    
    # Risk: Do we crash immediately?
    # Count where drawdown < -5%
    crashes = len(res[res['draw_1'] <= -0.05])
    print(f"Risk of -5% Drop: {crashes} ({crashes/count*100:.1f}%)")
    
    # 4. Filtered Late Entry (Wait for Green Bar 1)
    print("\n--- FILTERED ENTRY: Only if Bar 1 is GREEN ---")
    green_bar1 = res[res['bar1_gain'] > 0]
    g_count = len(green_bar1)
    g_wins = len(green_bar1[green_bar1['rem_gain_1'] >= 0.10])
    print(f"Entries: {g_count} ({g_count/count*100:.1f}% of rockets)")
    print(f"Prob of catching +10% MORE: {g_wins/g_count*100:.1f}%")
    
    # 5. Filtered Late Entry + High Vol Bar 1
    print("\n--- SUPER FILTER: Green Bar 1 + Vol > 2x ---")
    super_bar1 = green_bar1[green_bar1['bar1_vol'] > 2.0]
    s_count = len(super_bar1)
    if s_count > 0:
        s_wins = len(super_bar1[super_bar1['rem_gain_1'] >= 0.10])
        print(f"Entries: {s_count}")
        print(f"Prob of catching +10% MORE: {s_wins/s_count*100:.1f}%")
    else:
        print("No matches.")

if __name__ == "__main__":
    analyze_rocket_continuation()
