
import pandas as pd
import numpy as np
import tezaver.core.coin_cell_paths as coin_cell_paths
from tezaver.core import config
# from tqdm import tqdm

def analyze_rocket_signature():
    print("=== ROCKET SIGNATURE ANALYZER ===")
    print("Searching for the 'Hidden DNA' of 30% Pumps.")
    print("Comparing: [ROCKETS (>30% in 11 bars)] vs [BASELINE (Random Noise)]")
    
    coins = config.DEFAULT_COINS
    
    # Feature Accumulators
    rocket_features = []
    baseline_features = []
    
    # We will sample baseline at 10x the rate of rockets? 
    # Or just collect all rockets and a random subset of others.
    
    for i, symbol in enumerate(coins):
        if i % 10 == 0: print(f"Scanning {i}/{len(coins)}...", end='\r')
        
        # Load 15m
        p15 = coin_cell_paths.get_history_file(symbol, "15m")
        if not p15.exists(): continue
        df15 = pd.read_parquet(p15)
        if df15.empty or len(df15) < 300: continue
        
        # Load 1h (MTF Context)
        # To merge, we need to align times.
        # Resampling 15m to 1h is easier/faster than loading 1h file and merging?
        # Loading 1h file is more accurate for indicators computed on 1h.
        p1h = coin_cell_paths.get_history_file(symbol, "1h")
        df1h = None
        if p1h.exists():
            df1h = pd.read_parquet(p1h)
        
        # --- FEATURE ENGINEERING (15m) ---
        # 1. RSI & EMA
        delta = df15['close'].diff()
        up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
        rs = up.ewm(com=13, adjust=False).mean() / down.ewm(com=13, adjust=False).mean()
        df15['rsi'] = 100 - (100 / (1 + rs))
        df15['rsi_ema'] = df15['rsi'].ewm(span=9).mean()
        
        # 2. MACD
        ema12 = df15['close'].ewm(span=12, adjust=False).mean()
        ema26 = df15['close'].ewm(span=26, adjust=False).mean()
        df15['macd'] = ema12 - ema26
        df15['macd_signal'] = df15['macd'].ewm(span=9, adjust=False).mean()
        df15['macd_hist'] = df15['macd'] - df15['macd_signal']
        
        # 3. Bollinger Bands (20, 2)
        sma20 = df15['close'].rolling(20).mean()
        std20 = df15['close'].rolling(20).std()
        df15['bb_upper'] = sma20 + 2 * std20
        df15['bb_lower'] = sma20 - 2 * std20
        df15['bb_width'] = (df15['bb_upper'] - df15['bb_lower']) / sma20
        # %B
        df15['bb_pct_b'] = (df15['close'] - df15['bb_lower']) / (df15['bb_upper'] - df15['bb_lower'])
        
        # 4. ATR%
        hl = df15['high'] - df15['low']
        # Simple ATR for speed
        df15['atr'] = hl.rolling(14).mean() 
        df15['atr_pct'] = df15['atr'] / df15['close']
        
        # 5. Volume
        df15['vol_sma50'] = df15['volume'].rolling(50).mean()
        df15['vol_factor'] = df15['volume'] / df15['vol_sma50']
        
        # 6. Trend (EMA 200)
        df15['ema50'] = df15['close'].ewm(span=50).mean()
        df15['ema200'] = df15['close'].ewm(span=200).mean()
        df15['trend_dist'] = (df15['close'] - df15['ema200']) / df15['ema200']
        
        # --- NEW FEATURES (Round 2) ---
        # 7. Distance to EMA50 (Support Check)
        df15['dist_ema50'] = (df15['close'] - df15['ema50']) / df15['ema50']
        
        # 8. Candle Body Ratio (Compression Check)
        # Ratio of Body to Total Range. Small ratio = Doji/Indecision.
        candle_range = df15['high'] - df15['low']
        body_size = (df15['close'] - df15['open']).abs()
        # Avoid div by zero
        df15['body_ratio'] = np.where(candle_range > 0, body_size / candle_range, 1.0)
        # Avg body ratio of last 3 bars
        df15['avg_body_ratio'] = df15['body_ratio'].rolling(3).mean()
        
        # 9. Stoch RSI (Oversold in Uptrend?)
        min_rsi = df15['rsi'].rolling(14).min()
        max_rsi = df15['rsi'].rolling(14).max()
        df15['stoch_k'] = (df15['rsi'] - min_rsi) / (max_rsi - min_rsi)
        
        # CLEANUP
        df15.dropna(inplace=True)
        
        # --- MTF MERGE (1h) ---
        if df1h is not None and not df1h.empty:
            # Calc 1h Indicators
            delta1h = df1h['close'].diff()
            up1h = delta1h.clip(lower=0)
            down1h = -1 * delta1h.clip(upper=0)
            rs1h = up1h.ewm(com=13, adjust=False).mean() / down1h.ewm(com=13, adjust=False).mean()
            df1h['rsi_1h'] = 100 - (100 / (1 + rs1h))
            
            # Align
            # Standardize Time Column for 15m
            if 'open_time' not in df15.columns:
                if 'datetime' in df15.columns: df15['open_time'] = pd.to_datetime(df15['datetime'])
                elif 'date' in df15.columns: df15['open_time'] = pd.to_datetime(df15['date'])
                elif 'timestamp' in df15.columns: df15['open_time'] = pd.to_datetime(df15['timestamp'])
                elif isinstance(df15.index, pd.DatetimeIndex): df15['open_time'] = df15.index
                else: df15['open_time'] = pd.NaT # Should handle this
            
            # Standardize Time Column for 1h
            if 'open_time' not in df1h.columns:
                if 'datetime' in df1h.columns: df1h['open_time'] = pd.to_datetime(df1h['datetime'])
                elif 'date' in df1h.columns: df1h['open_time'] = pd.to_datetime(df1h['date'])
                elif 'timestamp' in df1h.columns: df1h['open_time'] = pd.to_datetime(df1h['timestamp'])
                elif isinstance(df1h.index, pd.DatetimeIndex): df1h['open_time'] = df1h.index
                else: df1h['open_time'] = pd.NaT

            # Drop invalid times
            df15.dropna(subset=['open_time'], inplace=True)
            df1h.dropna(subset=['open_time'], inplace=True)
            
            # Ensure datetime type
            df15['open_time'] = pd.to_datetime(df15['open_time'], utc=True)
            df1h['open_time'] = pd.to_datetime(df1h['open_time'], utc=True)
            
            # Ensure datetime
            df15['key_1h'] = df15['open_time'].dt.floor('h')
            df1h['key_1h'] = df1h['open_time']
            
            # Merge
            df1h_sub = df1h[['key_1h', 'rsi_1h']].copy()
            df15 = pd.merge(df15, df1h_sub, on='key_1h', how='left')
            
        else:
            df15['rsi_1h'] = np.nan

        # --- LABELING ---
        # Future Gain 30% in 11 bars
        # Roll forward max
        # df15['future_high'] = df15['high'].shift(-1).rolling(11).max()
        # forward rolling is tricky in pandas < 1.1 without fixer.
        # But we can simply reverse, roll, unreverse.
        rev_high = df15['high'].iloc[::-1]
        rev_roll = rev_high.rolling(11).max()
        df15['future_max_high'] = rev_roll.iloc[::-1].shift(-1) # Shift -1 to exclude current bar from future
        
        df15['future_gain'] = (df15['future_max_high'] - df15['close']) / df15['close']
        
        # Define Group
        # ROCKET: Gain > 0.30
        is_rocket = df15['future_gain'] >= 0.30
        
        rockets = df15[is_rocket]
        # Columns to analyze
        feat_cols = ['rsi', 'rsi_ema', 'macd_hist', 'bb_width', 'bb_pct_b', 'atr_pct', 'vol_factor', 'trend_dist', 'rsi_1h',
                     'dist_ema50', 'avg_body_ratio', 'stoch_k']
                     
        if not rockets.empty:
            # Extract Features
            feats = rockets[feat_cols].values
            # Filter NaNs
            feats = feats[~np.isnan(feats).any(axis=1)]
            rocket_features.extend(feats)
            
        # BASELINE: Sample random 5% of non-rockets
        baseline = df15[~is_rocket].sample(frac=0.01) # 1% enough for baseline
        if not baseline.empty:
            feats = baseline[feat_cols].values
            feats = feats[~np.isnan(feats).any(axis=1)]
            baseline_features.extend(feats)

    # --- STATISTICAL COMPARISON ---
    print("\n\n=== ANALYSIS COMPLETE ===")
    print(f"Rockets Collected: {len(rocket_features)}")
    print(f"Baseline Samples: {len(baseline_features)}")
    
    if len(rocket_features) < 10:
        print("Not enough rockets found for stats.")
        return
        
    cols = ['RSI (15m)', 'RSI EMA', 'MACD Hist', 'BB Width', 'BB %B', 'ATR%', 'Vol Factor', 'Trend Dist (EMA200)', 'RSI (1h)',
            'Dist EMA50', 'Body Ratio (3)', 'Stoch K']
    
    r_arr = np.array(rocket_features)
    b_arr = np.array(baseline_features)
    
    print(f"\n{'FEATURE':<20} | {'ROCKET MEAN':<12} | {'BASE MEAN':<12} | {'DIFFERENCE':<12} | {'Z-SCORE':<8}")
    print("-" * 75)
    
    for i, name in enumerate(cols):
        r_mean = np.mean(r_arr[:, i])
        b_mean = np.mean(b_arr[:, i])
        r_std = np.std(r_arr[:, i])
        b_std = np.std(b_arr[:, i])
        
        diff = r_mean - b_mean
        pct_diff = (diff / abs(b_mean)) * 100 if b_mean != 0 else 0
        
        # Simple separation metric
        # (Mean1 - Mean2) / AvgStd
        sep = diff / ((r_std + b_std)/2)
        
        # Formatting
        if name in ['BB Width', 'ATR%', 'Trend Dist', 'Dist EMA50']:
             r_s = f"{r_mean*100:.2f}%"
             b_s = f"{b_mean*100:.2f}%"
        else:
             r_s = f"{r_mean:.2f}"
             b_s = f"{b_mean:.2f}"
             
        score_mark = ""
        if abs(sep) > 0.5: score_mark = "🔥"
        if abs(sep) > 1.0: score_mark = "🔥🔥"
        
        print(f"{name:<20} | {r_s:<12} | {b_s:<12} | {pct_diff:>+9.1f}% | {sep:>5.2f} {score_mark}")

    print("-" * 75)
    print("Interpretation:")
    print("- Z-Score > 0.5: Significant Difference.")
    print("- Z-Score > 1.0: Very Strong Differentiator.")

if __name__ == "__main__":
    analyze_rocket_signature()
