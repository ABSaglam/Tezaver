
import sys
from pathlib import Path
import pandas as pd
import logging
import os

# Add src to path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root / "src"))

from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
from tezaver.core.logging_utils import get_logger

# Setup logging
logging.basicConfig(level=logging.INFO)

def verify():
    symbol = "BTCUSDT"
    print(f"Running refined Oracle Mode scan for {symbol}")
    
    try:
        # Run scan
        result = run_fast15_scan_for_symbol(symbol)
        
        # Load results manually to check for overlaps
        output_path = result.output_path
        if os.path.exists(output_path):
             df = pd.read_parquet(output_path)
             print(f"Total Unique Events: {len(df)}")
             
             # Check for duplicates using time overlaps
             # event_time is start. Approximate end time = event_time + (bars_to_peak * 15m)
             # Note: This is an approximation since markets have gaps, but good enough for rough overlap check.
             
             # Convert bars to peak to timedelta
             df['duration'] = pd.to_timedelta(df['bars_to_peak'] * 15, unit='m')
             df['end_time'] = df['event_time'] + df['duration']
             
             # Sort by end time to likely cluster duplicates
             df = df.sort_values('end_time')
             
             # Check if any end_time is identical or very close to another
             # We look for EXACT matches on end_time as a proxy for "same peak"
             duplicates = df[df.duplicated('end_time', keep=False)]
             
             if not duplicates.empty:
                 print(f"WARNING: Found {len(duplicates)} events sharing the same estimated peak time (overlap potential).")
                 print(duplicates[['event_time', 'bars_to_peak', 'end_time', 'future_max_gain_pct']])
             else:
                 print("✅ SUCCESS: No overlapping rallies pointing to the same peak.")
                 
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify()
