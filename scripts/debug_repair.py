import pandas as pd
import os

def debug_failures():
    trouble_coins = ['AERGOUSDT', 'AGIXUSDT']
    root = "coin_cells"
    
    for coin in trouble_coins:
        path = os.path.join(root, coin, "data", "history_1d.parquet")
        print(f"--- DEBUGGING {coin} ---")
        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                print(f"File Size: {os.path.getsize(path)} bytes")
                print(f"Rows: {len(df)}")
                print(f"Columns: {list(df.columns)}")
                print("Head:")
                print(df.head())
                print("Tail:")
                print(df.tail())
                
                # Check timestamps
                print(f"Start: {pd.to_datetime(df['timestamp'].min(), unit='ms')}")
                print(f"End: {pd.to_datetime(df['timestamp'].max(), unit='ms')}")
            except Exception as e:
                print(f"❌ READ FAIL: {e}")
        else:
            print("❌ FILE NOT FOUND!")

if __name__ == "__main__":
    debug_failures()
