
from tezaver.engines.tunnel_engine import TunnelEngine
import pandas as pd
import os

def debug_jan28_values():
    print("--- 28 OCAK DEĞER KONTROLÜ ---")
    
    engine = TunnelEngine()
    target_date = pd.Timestamp("2026-01-28")
    
    # Check a few diverse coins
    test_coins = ["AVNTUSDT", "BTCUSDT", "JTOUSDT", "PUMPUSDT"]
    
    for symbol in test_coins:
        print(f"\nScanning {symbol}...")
        path_15m = os.path.join(engine.cells_dir, symbol, "data", "history_15m.parquet")
        
        if not os.path.exists(path_15m): 
            print("No Data")
            continue
            
        df = pd.read_parquet(path_15m)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        
        # 1. Calc Hist
        engine._calculate_indicators(df)
        
        # 2. Slice Jan 28
        mask = (df.index.normalize() == target_date)
        day_df = df[mask].copy()
        
        if day_df.empty:
            print("❌ No candles for Jan 28 yet.")
            print(f"Last candle was: {df.index[-1]}")
            continue
            
        print(f"✅ Found {len(day_df)} candles for Jan 28.")
        
        # 3. Print Values
        for idx, row in day_df.iterrows():
            time_str = idx.strftime('%H:%M')
            price_chg = ((row['close'] - row['open']) / row['open']) * 100
            
            # Check custom cols
            v100 = row.get('v_100', 0)
            angle = row.get('angle_eda', 0)
            
            print(f"[{time_str}] P: {price_chg:+.2f}% | V100: {v100:.2f} | ANG: {angle:.2f}")

            # Check Trigger Conditions manually
            if price_chg > 3.0 or v100 > 1.5:
                print("   ⚠️  SHOULD HAVE TRIGGERED!")

if __name__ == "__main__":
    debug_jan28_values()
