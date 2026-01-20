
import sys
import os
import pandas as pd
import numpy as np
import itertools

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def calculate_4h_indicators(df):
    # Standard
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Lock State Components
    df['dist_9_21'] = (df['ema_9'] / df['ema_21'] - 1) * 100
    df['dist_21_50'] = (df['ema_21'] / df['ema_50'] - 1) * 100
    df['dist_50_200'] = (df['ema_50'] / df['ema_200'] - 1) * 100
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Vol
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Candle Body
    df['body_size'] = abs(df['close'] - df['open']) / df['open'] * 100
    
    return df

def main():
    symbol = 'ALGOUSDT'
    print(f"🧬 4H LOCK-STATE EVOLUTION: {symbol}")
    print("="*70)

    # 1. Load Data
    # Daily Rallies (Target)
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    
    # 4H Data (Source)
    # Assuming standard path or I need to update coin_cell_paths to handle 4H if it doesn't already
    # For now I know where I saved it: coin_cells/ALGOUSDT/data/history_4h.parquet
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ 4H Data not found!")
        return
        
    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df = calculate_4h_indicators(df)
    
    # MAP TARGET ONTO 4H
    # A 4H candle is a "Pre-Rally" candle if it belongs to the "Day Before" a Rally Day.
    # Actually, simpler: A 4H candle is a "Signal" if the *next 24h* contains a Rally Start.
    # But let's stick to the prompt: "Check at Start of Day". 
    # So we look at the 4H candle that CLOSES just before the Daily Open (00:00 UTC).
    # That would be the 20:00-00:00 candle or similar.
    # Let's check 4H candles at 00:00 UTC (The 'Gate' candle).
    
    # Filter only 00:00 candles? No, let's check EVERY 4H candle as a potential entry.
    # If ANY 4H candle passes the key, does it lead to a rally within 24h?
    
    # Let's map "Is Rally Incoming?" (Target)
    # True if a Rally starts within 24h hours.
    
    df['target'] = False
    
    # Create a set of rally dates for fast lookup
    rally_dates = set(rally_results.keys())
    
    # This is slow, but accurate
    # For each row, check if (datetime + 24h).date() is in rally_dates
    # Actually, rally_results keys are "The Rally Day".
    # So if I am at 2023-01-01 12:00, and rally represents 01-02, then yes.
    
    # Optimized mapping:
    # df['next_day'] = (df['datetime'] + pd.Timedelta(hours=24)).dt.date
    # df['target'] = df['next_day'].isin(rally_dates)
    # Wait, rally starts on date D. We want to detect it on D-1 or D(00:00).
    # Let's say we scan at 00:00, 04:00, 08:00... 
    # If we find a signal at 16:00 on D-1, and rally is D, that's valid.
    
    vals = df['datetime'].dt.date.values
    
    # We want to catch the rally the day BEFORE it happens (Setup) or the Day OF (Early entry)
    # Let's target: Is today or tomorrow a Rally Day?
    
    # Vectorized approach
    is_rally_day = df['datetime'].dt.date.isin(rally_dates)
    is_pre_rally_day = (df['datetime'] + pd.Timedelta(days=1)).dt.date.isin(rally_dates)
    
    df['target'] = is_rally_day # Let's focus on entering ON the day or just before.
    
    total_candles = len(df)
    target_candles = df['target'].sum()
    print(f"Total 4H Candles: {total_candles}")
    print(f"Target Candles (Rally Days): {target_candles}")
    
    # INVERTED LOGIC: CHAOS THEORY
    # Search for Extreme Volume + Extreme Momentum
    
    param_grid = list(itertools.product(
        [65, 70, 75],        # rsi_min (High RSI only)
        [5, 10],             # ema_dist_min
        [2.0, 3.0, 4.0],     # vol_MIN (Require explosion)
        [True]               # macd_pos
    ))
    
    print(f"Testing {len(param_grid)} CHAOS Lock-States...")
    
    best_prec = 0
    best_rule = ""
    best_stats = {}
    
    for r_min, e_min, v_min, m_pos in param_grid:
        mask = (
            (df['rsi'] >= r_min) &
            (df['dist_21_50'] >= e_min) &
            (df['vol_ratio'] >= v_min) # REQUIRE HIGH VOLUME
        )
        if m_pos:
            mask = mask & (df['macd_hist'] > 0)
            
        hits = df[mask & df['target']]
        fails = df[mask & ~df['target']]
        
        h = len(hits)
        f = len(fails)
        t = h + f
        
        if t >= 3:
            prec = h/t*100
            if prec > best_prec:
                best_prec = prec
                best_rule = f"CHAOS: RSI>={r_min}, Trend>={e_min}, Vol>={v_min}"
                best_stats = {'h':h, 'f':f, 'p':prec}
                
                if prec >= 50:
                    print(f"🔥 CHAOS CANDIDATE: {best_rule} -> {h}/{t} ({prec:.1f}%)")
                    
    print("\n" + "="*70)
    print(f"🏆 BEST CHAOS KEY: {best_rule}")
    print(f"   Stats: {best_stats.get('h')} / {best_stats.get('h',0)+best_stats.get('f',0)} ({best_stats.get('p',0):.1f}%)")
    
    if best_stats.get('p', 0) >= 80:
         print("✅ Chaos Teorisi Çalıştı!")
    else:
         print("❌ Chaos Teorisi de Çalışmadı (%80 altı).")
                    
    print("\n" + "="*70)
    print(f"🏆 BEST 4H LOCK-STATE: {best_rule}")
    print(f"   Stats: {best_stats.get('h')} / {best_stats.get('h',0)+best_stats.get('f',0)} ({best_stats.get('p',0):.1f}%)")
    
    if best_stats.get('p', 0) == 100:
        print("✅ Bu anahtar, 4H grafikte ralli olmayan hiçbir mumu geçirmedi.")
    else:
        print("⚠️ 4H analizinde de %100 filtrelenmiş durum bulunamadı.")

if __name__ == "__main__":
    main()
