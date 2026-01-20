
import sys
import os
import pandas as pd
from datetime import date

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AGLDUSDT'
    print(f"🔬 DCH FORENSICS: {symbol}")
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Calculate indicators
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    
    # Upper Shadows
    # Upper Shadow = High - max(open, close)
    # Range = High - Low
    df['max_body'] = df[['open', 'close']].max(axis=1)
    df['upper_shadow'] = df['high'] - df['max_body']
    df['range'] = df['high'] - df['low']
    df['upper_shadow_ratio'] = df['upper_shadow'] / df['range']
    
    # Target Dates
    # Failures remaining after Vol Cap < 5.0:
    fail_dates = [
        date(2023, 4, 12),
        date(2023, 7, 17),
        date(2024, 11, 10)
    ]
    
    # Hits (High Mom):
    hit_dates = [
        date(2023, 7, 18),
        date(2023, 7, 19),
        date(2023, 10, 23),
        date(2023, 12, 25),
        date(2024, 12, 25),
        date(2024, 12, 29),
        date(2025, 1, 2)
    ]
    
    print("\n--- FAILURES ---")
    for d in fail_dates:
        row = df[df['datetime'].dt.date == d]
        if not row.empty:
            r = row.iloc[0]
            print(f"FAIL: {d} | M5:{r['mom_5d']:.1f} | US:{r['upper_shadow_ratio']:.2f} | DCH:{r['daily_ch']:.1f}")
            
    print("\n--- HITS ---")
    for d in hit_dates:
        row = df[df['datetime'].dt.date == d]
        if not row.empty:
            r = row.iloc[0]
            print(f"HIT : {d} | M5:{r['mom_5d']:.1f} | US:{r['upper_shadow_ratio']:.2f} | DCH:{r['daily_ch']:.1f}")

if __name__ == "__main__":
    main()
