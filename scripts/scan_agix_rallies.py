
import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import TIME_LABS_LOOKAHEAD_BARS, TIME_LABS_MIN_GAIN, TIME_LABS_RALLY_BUCKETS, TIME_LABS_EVENT_GAP
from tezaver.rally.time_labs_scanner import run_timeframe_rally_scan_for_symbol
from tezaver.core.logging_utils import get_logger

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)

def main():
    symbol = "AGIXUSDT"
    print(f"🚀 Scanning rallies for {symbol} (1d)...")
    
    try:
        run_timeframe_rally_scan_for_symbol(
            symbol=symbol,
            timeframe="1d",
            lookahead=TIME_LABS_LOOKAHEAD_BARS["1d"],
            min_gain=TIME_LABS_MIN_GAIN["1d"],
            buckets=TIME_LABS_RALLY_BUCKETS,
            event_gap=TIME_LABS_EVENT_GAP["1d"]
        )
        print(f"✅ Scan complete for {symbol}")
        
    except Exception as e:
        print(f"❌ Scan failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
