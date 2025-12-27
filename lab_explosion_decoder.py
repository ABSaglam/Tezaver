
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def load_data(symbol, tf):
    path = Path(f"coin_cells/{symbol}/data/history_{tf}.parquet")
    if not path.exists(): return None
    df = pd.read_parquet(path)
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.set_index('open_time').sort_index()
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def run_decoder():
    symbol = "ADAUSDT"
    print(f"🔥 EXPLOSION DECODER ACTIVATED: {symbol}")
    
    # 1. Load Multi-TF Data
    df_15m = load_data(symbol, "15m")
    df_1h = load_data(symbol, "1h")
    df_4h = load_data(symbol, "4h")
    
    if df_15m is None or df_1h is None:
        print("Data missing.")
        return

    # 2. Enrich 1H and 4H (Context Layers)
    # 1H Context
    df_1h['rsi'] = calculate_rsi(df_1h['close'], 14)
    df_1h['body_size'] = (df_1h['close'] - df_1h['open']).abs() / df_1h['open'] * 100
    df_1h['ma50'] = df_1h['close'].rolling(50).mean()
    
    # 4H Context
    df_4h['ma200'] = df_4h['close'].rolling(200).mean() # Major Trend
    
    # 3. Identify Explosions in 15m (The Event)
    # Logic: Range > 3% AND Volume > 3x Avg
    df_15m['range_pct'] = (df_15m['high'] - df_15m['low']) / df_15m['open'] * 100
    df_15m['close_pct'] = (df_15m['close'] - df_15m['open']) / df_15m['open'] * 100 # Body return
    
    df_15m['vol_ma50'] = df_15m['volume'].rolling(50).mean()
    df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_ma50']
    
    # PRE-EVENT Volatility
    sma20 = df_15m['close'].rolling(20).mean()
    std20 = df_15m['close'].rolling(20).std()
    df_15m['bb_width'] = (std20 * 2) / sma20 * 100
    df_15m['pre_bb_width'] = df_15m['bb_width'].shift(1) # Width BEFORE explosion
    
    # Filter: Explosions
    explosions = df_15m[
        (df_15m['close_pct'] > 3.0) &  # Big Green Candle
        (df_15m['vol_ratio'] > 3.0)    # Huge Volume
    ].copy()
    
    print(f"💥 DETECTED EXPLOSIONS: {len(explosions)}")
    
    # 4. Analyze Outcomes & Context
    results = []
    
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=32)
    df_15m['future_max'] = df_15m['close'].rolling(window=indexer).max()
    
    for time, row in explosions.iterrows():
        # Get Outcome
        entry_price = row['close']
        future_high = df_15m.loc[time]['future_max'] # Lookahead already calculated
        # (Note: rolling max includes current bar, so need ensuring lookahead logic is correct. 
        # Actually simplest is to re-slice for accuracy)
        
        future = df_15m.loc[time:].iloc[1:33]
        if future.empty: continue
        
        real_max = future['close'].max()
        gain = (real_max - entry_price) / entry_price * 100
        
        is_winner = gain > 5.0 # True Breakout
        is_loser  = gain < 1.0 # Fakeout
        
        if not is_winner and not is_loser: continue # Middle ground ignored
        
        # Get Context (Time Alignment)
        # Find 1H bar containing this 15m time
        # Floor to hour
        time_1h = time.floor('h')
        ctx_1h = df_1h.loc[:time_1h].iloc[-1] if time_1h in df_1h.index else None
        if ctx_1h is None: 
            # Try to get strictly previous 1h
             ctx_1h = df_1h.loc[:time].iloc[-1]
             
        # Find 4H trend
        time_4h = time.floor('4h')
        ctx_4h = df_4h.loc[:time_4h].iloc[-1] if time_4h in df_4h.index else df_4h.loc[:time].iloc[-1]
        
        # Features
        res = {
            'time': time,
            'result': 'WINNER' if is_winner else 'LOSER',
            'gain': gain,
            
            # 1. Explosion Quality
            'vol_ratio': row['vol_ratio'],
            'body_wick_ratio': row['close_pct'] / row['range_pct'], # 1.0 = Full Body, 0.5 = Half Wick
            'pre_volatility': row['pre_bb_width'],
            
            # 2. 1H Context
            'rsi_1h': ctx_1h['rsi'] if ctx_1h is not None else 50,
            'dist_ma50_1h': ((ctx_1h['close'] - ctx_1h['ma50'])/ctx_1h['ma50']*100) if ctx_1h is not None else 0,
            
            # 3. 4H Context
            'trend_4h': ((row['close'] - ctx_4h['ma200'])/ctx_4h['ma200']*100) if ctx_4h is not None else 0
        }
        results.append(res)
        
    res_df = pd.DataFrame(results)
    
    # 5. The Cipher (Comparison)
    print("\n" + "="*60)
    print("🔓 EXPLOSION DECODER REPORT: Real vs Fake")
    print("="*60)
    
    winners = res_df[res_df['result'] == 'WINNER']
    losers = res_df[res_df['result'] == 'LOSER']
    
    print(f"WINNERS: {len(winners)}")
    print(f"LOSERS:  {len(losers)}")
    print(f"WIN RATE (Base): {len(winners)/len(res_df)*100:.1f}%")
    
    print("\n--- THE DIFFERENCE (CIPHER) ---")
    features = [
        ('body_wick_ratio', 'Candle Quality (1=Full)'),
        ('pre_volatility',  'Pre-Event Squeeze (Width)'),
        ('vol_ratio',       'Volume Magnitude'),
        ('rsi_1h',          '1H RSI Context'),
        ('trend_4h',        '4H Trend (vs MA200)')
    ]
    
    print(f"{'FEATURE':<20} | {'WINNER':<10} | {'LOSER':<10} | {'DIFF':<10}")
    print("-" * 60)
    
    for col, name in features:
        w = winners[col].mean()
        l = losers[col].mean()
        diff = w - l
        print(f"{name:<20} | {w:<10.2f} | {l:<10.2f} | {diff:<+10.2f}")
        
    print("-" * 60)
    
    # Rules Extraction
    # Hypothesis check: Pre-Volatility > 2.0 (Expansion) AND 1H RSI < 70 (Room to grow)
    print("\n--- HYPOTHETICAL RULES TEST ---")
    
    # Rule 1: "Fresh Fuel" -> 1H RSI < 70
    rule1_pass = res_df[res_df['rsi_1h'] < 70]
    wr1 = len(rule1_pass[rule1_pass['result']=='WINNER']) / len(rule1_pass) * 100
    print(f"Rule 1 (1H RSI < 70): Win Rate {wr1:.1f}% (Count: {len(rule1_pass)})")
    
    # Rule 2: "Solid Body" -> Body/Wick > 0.8
    rule2_pass = res_df[res_df['body_wick_ratio'] > 0.8]
    wr2 = len(rule2_pass[rule2_pass['result']=='WINNER']) / len(rule2_pass) * 100
    print(f"Rule 2 (Solid Candle): Win Rate {wr2:.1f}% (Count: {len(rule2_pass)})")
    
    # Rule 3: "Active Zone" -> Pre-Vol > 1.5
    rule3_pass = res_df[res_df['pre_volatility'] > 1.5]
    wr3 = len(rule3_pass[rule3_pass['result']=='WINNER']) / len(rule3_pass) * 100
    print(f"Rule 3 (Active Zone):  Win Rate {wr3:.1f}% (Count: {len(rule3_pass)})")

    # COMBO
    combo = res_df[
        (res_df['rsi_1h'] < 70) & 
        (res_df['body_wick_ratio'] > 0.8) &
        (res_df['pre_volatility'] > 1.5)
    ]
    wr_combo = len(combo[combo['result']=='WINNER']) / len(combo) * 100 if len(combo) > 0 else 0
    print(f"GOLDEN COMBO:          Win Rate {wr_combo:.1f}% (Count: {len(combo)})")

if __name__ == "__main__":
    run_decoder()
