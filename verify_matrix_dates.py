import pandas as pd
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from tezaver.data.history_loader import load_single_coin_history

coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "DOGEUSDT", "XRPUSDT"]
print("Checking coin history indices...")

for coin in coins:
    print(f"--- {coin} ---")
    df = load_single_coin_history(coin, "1h")
    if df is None or df.empty:
        print("  No data found.")
        continue
    
    print(f"  Index Type: {type(df.index)}")
    print(f"  Min Date: {df.index.min()}")
    print(f"  Max Date: {df.index.max()}")
    print(f"  Sample: {df.index[:3]}")
    
    # Check for 1970
    if df.index.min().year == 1970:
        print("  WARNING: 1970 date found!")
