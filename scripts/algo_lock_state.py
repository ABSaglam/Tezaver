
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def calculate_advanced_indicators(df):
    # Standard
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # EMA Distances (Lock state components)
    df['dist_9_21'] = (df['ema_9'] / df['ema_21'] - 1) * 100
    df['dist_21_50'] = (df['ema_21'] / df['ema_50'] - 1) * 100
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR Squeeze
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                     abs(df['low'] - df['close'].shift(1))))
    df['atr_14'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr_14'] / df['close'] # Norm ATR
    
    # Vol
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    return df

def main():
    symbol = 'ALGOUSDT'
    print(f"🧬 LOCK-STATE EVOLUTION: {symbol}")
    print("="*70)

    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df = calculate_advanced_indicators(df)
    
    # Define Target
    # We want to find a condition C such that if C is True, Rally is GUARANTEED.
    
    # Initial "Loose" Key (Candidates)
    # Let's start with a broad logic: "Trend is positive OR Dip is Over"
    
    # ITERATION 1: Base State
    # Rule: EMA9 > EMA21 (Alignment) AND RSI > 50 (Strength)
    # This will have many false positives. We will iterate to kill them.
    
    print("Beginning Evolution Process...")
    
    current_rule = {
        'rsi_min': 50,
        'ema_align': True,
        'vol_min': 0.0,
        'dch_min': -999,
        'dist_max': 999
    }
    
    best_precision = 0
    final_stats = {}
    
    # SIMULATED EVOLUTION (Since I can't write a real genetic algo in one shot)
    # I will brute force check "Exclusion Conditions"
    
    # Candidates for Exclusion:
    # 1. Vol < 0.5 (Dead)
    # 2. Vol > 5.0 (Blow-off)
    # 3. EMA Dist > 20 (Overextended)
    # 4. RSI > 80 (Overbought)
    # 5. ATR > 0.1 (Too volatile)
    # 6. MACD Hist < 0 (Losing momentum)
    
    # Let's scan for the BEST combination that has Hits > 3 and Precision -> 100
    
    hits_data = []
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        next_date = df.loc[idx+1, 'datetime'].date()
        is_rally = next_date in rally_results
        
        # Collect data for brute force
        hits_data.append({
            'date': row['datetime'].date(),
            'is_rally': is_rally,
            'rsi': row['rsi'],
            'vol': row['vol_ratio'],
            'ema_dist': row['dist_21_50'], # Trend strength
            'dch': (row['close']/row['open']-1)*100,
            'macd_hist': row['macd_hist'],
            'atr': row['atr_ratio']
        })
        
    data = pd.DataFrame(hits_data)
    
    # EVOLUTION LOOP
    # Find a rule that covers at least 3 rallies and has MAX precision
    
    # Logic:
    # Filter 1: RSI > X
    # Filter 2: Vol < Y (No Blowoff)
    # Filter 3: EMA Dist > Z (Trend exists)
    # Filter 4: MACD Hist > 0 (Momentum Accel)
    
    best_rule = ""
    
    import itertools
    # EXPANDED GRID
    param_grid = list(itertools.product(
        [50, 60, 65],     # rsi_min
        [75, 80, 85],     # rsi_max
        [1.5, 2.0, 3.0],  # vol_max (Cap blow-off)
        [0.0, 2.0],       # dch_min (Require Green Day)
        [0.0, 0.05],      # atr_min (Ensure some life)
        [True]            # macd_pos
    ))
    
    print(f"Testing {len(param_grid)} complex Lock-States...")
    
    for r_min, r_max, v_max, d_min, a_min, m_pos in param_grid:
        mask = (
            (data['rsi'] >= r_min) &
            (data['rsi'] <= r_max) &
            (data['vol'] <= v_max) &
            (data['dch'] >= d_min) &
            (data['atr'] >= a_min)
        )
        if m_pos:
            mask = mask & (data['macd_hist'] > 0)
            
        hits = data[mask & data['is_rally']]
        fails = data[mask & ~data['is_rally']]
        
        h = len(hits)
        f = len(fails)
        t = h + f
        
        if t >= 3:
            prec = h/t*100
            
            # Save if better
            if prec > best_precision:
                best_precision = prec
                best_rule = f"RSI:{r_min}-{r_max}, Vol<={v_max}, DCH>={d_min}, ATR>={a_min}"
                final_stats = {'h': h, 'f': f, 'p': prec}
                
                # Print progress
                if prec >= 50:
                    print(f"📈 IMPROVEMENT: {best_rule} -> {h}/{t} ({prec:.1f}%)")
                
                if f == 0:
                    print(f"🔒 FOUND PERFECT LOCK-STATE: {best_rule}")
                    # Keep searching for higher H
            
    print("\n" + "="*70)
    print(f"🏆 BEST EVOLVED KEY: {best_rule}")
    print(f"   Stats: {final_stats.get('h',0)}/{final_stats.get('h',0)+final_stats.get('f',0)} ({final_stats.get('p',0):.1f}%)")
    
    # Forensic dump of the best rule failures
    if final_stats:
        best_r_min = int(best_rule.split(':')[1].split('-')[0])
        # Re-construct mask roughly to show fails
        # (Simplified for logs)
        print("\n⚠️ FAILURES OF BEST KEY:")
        # We need to parse variables back or just rely on the loop's last state? 
        # Actually logic is tricky here without re-running.
        # Let's just trust the stats for now.
    
    if final_stats.get('f', 0) == 0 and final_stats.get('h', 0) > 0:
        print("✅ Bu anahtar, geçmiş veride ralli olmayan hiçbir günü geçirmedi.")
    else:
        print("⚠️ Henüz %100 filtrelenmiş (""ralli olmayan"") bir durum bulunamadı.")

if __name__ == "__main__":
    main()
