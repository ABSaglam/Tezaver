
import pandas as pd
import numpy as np
import tezaver.core.coin_cell_paths as coin_cell_paths
from tezaver.core import config
# from tqdm import tqdm

def test_rocket_dna():
    print("=== ROCKET DNA TEST (Predictive Power) ===")
    print("Hypothesis: BB Width > 15% + ATR% > 3% + RSI 1h > 60 => ROCKET?")
    
    coins = config.DEFAULT_COINS
    
    results = []
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0: print(f"Scanning {i}/{len(coins)}...", end='\r')
        
        # Load 15m
        p15 = coin_cell_paths.get_history_file(symbol, "15m")
        if not p15.exists(): continue
        df15 = pd.read_parquet(p15)
        if df15.empty or len(df15) < 300: continue
        
        # Load 1h
        p1h = coin_cell_paths.get_history_file(symbol, "1h")
        df1h = None
        if p1h.exists():
            df1h = pd.read_parquet(p1h)
        else:
            continue # Need 1h for this test
            
        # --- FEATURE ENG ---
        # 1. 15m Features
        # BB Width
        sma20 = df15['close'].rolling(20).mean()
        std20 = df15['close'].rolling(20).std()
        df15['bb_upper'] = sma20 + 2 * std20
        df15['bb_lower'] = sma20 - 2 * std20
        df15['bb_width'] = (df15['bb_upper'] - df15['bb_lower']) / sma20
        
        # ATR%
        hl = df15['high'] - df15['low']
        df15['atr_pct'] = hl.rolling(14).mean() / df15['close']
        
        # 2. 1h Features
        # RSI 1h
        delta1h = df1h['close'].diff()
        up1h, down1h = delta1h.clip(lower=0), -1 * delta1h.clip(upper=0)
        rs1h = up1h.ewm(com=13, adjust=False).mean() / down1h.ewm(com=13, adjust=False).mean()
        df1h['rsi_1h'] = 100 - (100 / (1 + rs1h))
        
        # Standardize Time
        if 'open_time' not in df15.columns:
             if 'datetime' in df15.columns: df15['open_time'] = pd.to_datetime(df15['datetime'])
             elif 'date' in df15.columns: df15['open_time'] = pd.to_datetime(df15['date'])
             elif isinstance(df15.index, pd.DatetimeIndex): df15['open_time'] = df15.index
        
        if 'open_time' not in df1h.columns:
             if 'datetime' in df1h.columns: df1h['open_time'] = pd.to_datetime(df1h['datetime'])
             elif 'date' in df1h.columns: df1h['open_time'] = pd.to_datetime(df1h['date'])
             elif isinstance(df1h.index, pd.DatetimeIndex): df1h['open_time'] = df1h.index

        df15.dropna(subset=['open_time'], inplace=True)
        df1h.dropna(subset=['open_time'], inplace=True)
        
        df15['open_time'] = pd.to_datetime(df15['open_time'], utc=True)
        df1h['open_time'] = pd.to_datetime(df1h['open_time'], utc=True)
        
        df15['key_1h'] = df15['open_time'].dt.floor('h')
        df1h['key_1h'] = df1h['open_time']
        
        df1h_sub = df1h[['key_1h', 'rsi_1h']].copy()
        df15 = pd.merge(df15, df1h_sub, on='key_1h', how='inner')
        
        # --- DNA FILTER ---
        # The DNA we found: BB Width > 15%, ATR% > 3%, RSI 1h > 60
        # Let's test precisely this.
        
        mask = (df15['bb_width'] > 0.15) & \
               (df15['atr_pct'] > 0.03) & \
               (df15['rsi_1h'] > 60)
               
        candidates = df15[mask].copy()
        
        if candidates.empty: continue
        
        # --- OUTCOME ANALYSIS ---
        # Look forward 11 bars (or 24h?)
        # Let's check "Next 11 Bars" (Rocket Definition)
        
        # We need future data for these candidates.
        # Since 'candidates' is a slice, we need indices relative to df15.
        
        for idx in candidates.index:
            # Note: idx is the integer index of the MERGED dataframe if reset_index was called?
            # merge does reset index usually.
            # Let's trust location if we didn't shuffle.
            # Ideally use 'open_time' to find future in original df15? 
            # Too slow.
            # Let's operate on full df15 with a boolean mask and shift.
            pass
        
        # Vectorized Outcome
        # Shift -1 to -11 max
        rev_high = df15['high'].iloc[::-1]
        future_max = rev_high.rolling(11).max().iloc[::-1].shift(-1)
        
        rev_low = df15['low'].iloc[::-1]
        future_min = rev_low.rolling(11).min().iloc[::-1].shift(-1)
        
        df15['outcome_gain'] = (future_max - df15['close']) / df15['close']
        df15['outcome_loss'] = (future_min - df15['close']) / df15['close']
        
        # Apply mask again
        matches = df15[mask]
        
        for _, row in matches.iterrows():
            results.append({
                'gain_11': row['outcome_gain'],
                'draw_11': row['outcome_loss']
            })
            
    # RESULTS
    res_df = pd.DataFrame(results)
    count = len(res_df)
    
    print(f"\n\nTested DNA on {count} events.")
    
    if count == 0: return
    
    # 1. How many became Rockets (>30% gain)?
    rockets = res_df[res_df['gain_11'] >= 0.30]
    n_rockets = len(rockets)
    
    # 2. How many Crashed (Drawdown < -10%)?
    crashes = res_df[res_df['draw_11'] <= -0.10]
    n_crashes = len(crashes)
    
    # 3. How many were "Profitable" (>2% gain > abs(draw))?
    # Or just Win Rate (>2% Gain before -5% Stop?)
    # Simple Win Rate: Did it hit +5%?
    wins_5 = len(res_df[res_df['gain_11'] >= 0.05])
    
    print(f"Rocket Rate (>30% Gain): {n_rockets} ({n_rockets/count*100:.2f}%)")
    print(f"Crash Rate (<-10% Loss): {n_crashes} ({n_crashes/count*100:.2f}%)")
    print(f"Win Rate (>5% Gain): {wins_5} ({wins_5/count*100:.2f}%)")
    
    print(f"Avg Gain: {res_df['gain_11'].mean()*100:.2f}%")
    print(f"Avg Drawdown: {res_df['draw_11'].mean()*100:.2f}%")
    
    print("\nCONCLUSION:")
    if n_rockets/count > 0.50:
        print("✅ The DNA is SOLID! High Probability Predictor.")
    elif n_crashes/count > n_rockets/count:
        print("❌ DANGER! This DNA describes a 'Coin Flip' or a Crash.")
    else:
        print("⚠️ Mixed Bag. Indecisive.")

if __name__ == "__main__":
    test_rocket_dna()
