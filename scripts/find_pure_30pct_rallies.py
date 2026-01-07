
import pandas as pd
import numpy as np
from tezaver.core import config, coin_cell_paths
# from tqdm import tqdm

def find_pure_rallies():
    print("=== PURE 30% RALLY SEEKER (Reverse Engineering) ===")
    print("Target: +30% Gain in next 11 Bars (2h 45m)")
    print("Context: Normal pre-market (No crash > 15% in prev 11 bars)")
    
    coins = config.DEFAULT_COINS
    results = []
    
    # Global Feature Stats Accumulator
    feature_stats = {
        'rsi': [],
        'vol_factor': [],
        'atr_pct': [],
        'prev_11_change': []
    }
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0: print(f"Processing {i}/{len(coins)}...", end='\r')
        try:
            p = coin_cell_paths.get_history_file(symbol, "15m")
            if not p.exists(): continue
            df = pd.read_parquet(p)
            if df.empty or len(df) < 100: continue
            
            # Indicators (Just for "What Happened" analysis, not for filtering)
            # RSI
            delta = df['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Vol SMA
            df['vol_sma50'] = df['volume'].rolling(50).mean()
            df['vol_factor'] = df['volume'] / df['vol_sma50']
            
            # ATR
            h_l = df['high'] - df['low']
            df['atr_pct'] = (h_l / df['close']).rolling(14).mean()
            
            # Future Gain (11 bars)
            # We want High of next 11 bars relative to Close(T)
            # Rolling Max of High(T+1..T+11)
            # Shift high backwards by 1, then rolling 11
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=11)
            df['future_high_11'] = df['high'].shift(-1).rolling(window=indexer, min_periods=11).max()
            df['future_gain'] = (df['future_high_11'] - df['close']) / df['close']
            
            # Previous Context (11 bars)
            # Min Low of prev 11 bars relative to Close(T)
            # Rolling Min of Low (window=11)
            df['prev_low_11'] = df['low'].rolling(window=11).min()
            df['prev_crash_depth'] = (df['prev_low_11'] - df['close']) / df['close'] 
            # Note: prev_crash_depth will be negative. e.g. -0.20 means low was 20% below current close.
            # Wait, user said "Crash and recovery".
            # If "Crash", then Price(T) is effectively "Recovery".
            # Crash means: The Low(T-11..T) was very low compared to Price(T-11).
            # User simply wants "Previous 11 bars didn't look like a disaster dump".
            # Let's use simpler metric: Change in last 11 bars.
            df['prev_11_change'] = (df['close'] - df['close'].shift(11)) / df['close'].shift(11)
            
            # FILTER
            # 1. Gain >= 30%
            c_gain = df['future_gain'] >= 0.30
            
            # 2. No Crash
            # Let's say we don't want a "V-Shape" from a -20% drop.
            # Implies Close(T) > Low(T-11..T) is obvious.
            # Maybe restrict Previous Decline not to be too huge?
            # User: "çekilme makul... 5-10%".
            # So Low(T-11..T) should not be < 0.85 * High(T-11..T)?
            # Or simpler:
            # Drop from T-11 Open to T Close is not < -15%?
            c_context = df['prev_11_change'] > -0.15 
            
            candidates = df[c_gain & c_context]
            
            for idx, row in candidates.iterrows():
                # Dedup: If we find 5 consecutive bars hitting 30%, pick one (Peak? First?)
                # We'll handle dedup later or just take all.
                
                # Check "Recovery from Crash" more strictly
                # Look at Low of previous 11 bars vs High of previous 11 bars
                # window = df.loc[idx - pd.Timedelta(minutes=15*11) : idx] # Approximate
                # Actually, row['prev_low_11'] is available.
                # If (row['high'].rolling(11).max() - row['prev_low_11']) / row['prev_low_11'] > 0.30?
                # That would be valid volatility.
                # User's "Crash" concern usually means "Don't confirm a bottom fishing bounce".
                # But a 30% pump IS a bounce often.
                # Let's stick to the simple -15% change filter.
                
                # Collect
                results.append({
                    'symbol': symbol,
                    'date': row['open_time'] if 'open_time' in row else idx,
                    'gain_11': row['future_gain'],
                    'prev_11_change': row['prev_11_change'],
                    'vol_factor': row['vol_factor'],
                    'rsi': row['rsi'],
                    'atr_pct': row['atr_pct']
                })
                
                feature_stats['rsi'].append(row['rsi'])
                feature_stats['vol_factor'].append(row['vol_factor'])
                feature_stats['atr_pct'].append(row['atr_pct'])
                feature_stats['prev_11_change'].append(row['prev_11_change'])
                
        except Exception:
            continue
            
    # REPORT
    count = len(results)
    print(f"\nFound {count} 'Pure 30% Rallies' (Next 11 Bars).")
    
    if count == 0:
        return

    res_df = pd.DataFrame(results)
    
    # 1. List Top Examples
    print("\n--- TOP EXAMPLES ---")
    print(res_df.sort_values('gain_11', ascending=False).head(10)[['symbol', 'date', 'gain_11', 'vol_factor']])
    
    # 2. What are the common traits?
    print("\n--- ANATOMY OF A 30% PUMP (What actually happens?) ---")
    print(f"Avg Vol Factor (At T): {np.mean(feature_stats['vol_factor']):.2f}x")
    print(f"Avg RSI (At T): {np.mean(feature_stats['rsi']):.2f}")
    print(f"Avg ATR% (Volatility): {np.mean(feature_stats['atr_pct'])*100:.2f}%")
    print(f"Avg Prev 11-Bar Change: {np.mean(feature_stats['prev_11_change'])*100:.2f}%")
    
    # 3. Clustering
    # Do they have High Vol?
    # Count how many had Vol > 5x
    high_vol_count = len([v for v in feature_stats['vol_factor'] if v > 5])
    print(f"\nHow many had the '5x Volume' signal? {high_vol_count} ({high_vol_count/count*100:.1f}%)")
    
    # Count how many had RSI > 70
    high_rsi_count = len([r for r in feature_stats['rsi'] if r > 70])
    print(f"How many had RSI > 70? {high_rsi_count} ({high_rsi_count/count*100:.1f}%)")
    
    # Count how many had Low Vol (<2x) - "Silent Assassins"
    silent_count = len([v for v in feature_stats['vol_factor'] if v < 2])
    print(f"How many were 'Silent' (Vol < 2x)? {silent_count} ({silent_count/count*100:.1f}%)")

if __name__ == "__main__":
    find_pure_rallies()
