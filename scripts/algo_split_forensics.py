
import sys
import os
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Add scripts to path for db_helper
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ALGOUSDT'
    print(f"🔬 SPLIT FORENSICS: {symbol}")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Simple Indicators
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / (-df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean()))))
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema_50'] - 1) * 100

    print("\n--- THE 14 WINNERS (Audit) ---")
    for idx in range(50, len(df)-1):
        next_date = df.loc[idx+1, 'datetime'].date()
        if next_date in rally_results:
            r = df.loc[idx]
            tier = rally_results[next_date][0]
            print(f"{r['datetime'].date()} ({tier}) | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f} | DCH:{r['daily_ch']:.1f} | E:{r['ema_dist']:.1f}")

if __name__ == "__main__":
    main()
