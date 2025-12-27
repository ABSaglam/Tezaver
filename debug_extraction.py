
import sys
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from tezaver.foundry.packaging_v1 import _extract_price_window
from tezaver.core.coin_cell_paths import get_history_file

symbol = "ADAUSDT"
timeframe = "15m"
# Example timestamp from the logs: 1752032700 (Seconds?)
# Wait, let's verify if this is seconds or ms.
# 1752032700 seconds = July 2025.
# If it's 2024 data, maybe it's 170... 
# Let's use a known timestamp or try the one from the log.
event_ts_seconds = 1752032700 
event_time_iso = pd.to_datetime(event_ts_seconds, unit='s').isoformat()

print(f"Testing extraction for {symbol} {timeframe} at {event_time_iso}")

df = _extract_price_window(symbol, timeframe, event_time_iso)

if df is not None:
    print(f"SUCCESS: Extracted {len(df)} rows.")
    print(df.head())
else:
    print("FAILURE: Returned None.")
    
# Debug history file manually
h_file = get_history_file(symbol, timeframe)
print(f"History file: {h_file}")
if h_file.exists():
    hdf = pd.read_parquet(h_file)
    print(f"Columns: {hdf.columns.tolist()}")
    if 'open_time' in hdf.columns:
        print(f"History Range: {hdf['open_time'].min()} to {hdf['open_time'].max()}")
    elif 'timestamp' in hdf.columns:
         print(f"History Range (timestamp): {hdf['timestamp'].min()} to {hdf['timestamp'].max()}")
else:
    print("History file validation failed.")
