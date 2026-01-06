
import sys
import os
from pathlib import Path
import logging
from datetime import datetime
import time

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
from tezaver.rally.time_labs_scanner import run_1h_rally_scan_for_symbol, run_4h_rally_scan_for_symbol
from tezaver.core.logging_utils import get_logger

# Configure logging
logging.basicConfig(
    filename='logs/full_rally_scan.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add stdout handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

def run_full_scan():
    logger.info("=" * 80)
    logger.info(f"STARTING FULL RALLY SCAN FOR {len(DEFAULT_COINS)} COINS")
    logger.info("=" * 80)
    
    success_count = 0
    fail_count = 0
    total_coins = len(DEFAULT_COINS)
    
    start_time = datetime.now()
    
    for i, symbol in enumerate(DEFAULT_COINS):
        try:
            logger.info(f"[{i+1}/{total_coins}] Scanning {symbol}...")
            
            # 1. 5m Scan (Time-Labs Engine)
            try:
                # Reuse generic runner for 5m
                from tezaver.core.config import TIME_LABS_LOOKAHEAD_BARS, TIME_LABS_MIN_GAIN, TIME_LABS_RALLY_BUCKETS, TIME_LABS_EVENT_GAP
                from tezaver.rally.time_labs_scanner import run_timeframe_rally_scan_for_symbol
                
                run_timeframe_rally_scan_for_symbol(
                    symbol=symbol,
                    timeframe="5m",
                    lookahead=TIME_LABS_LOOKAHEAD_BARS["5m"],
                    min_gain=TIME_LABS_MIN_GAIN["5m"],
                    buckets=TIME_LABS_RALLY_BUCKETS,
                    event_gap=TIME_LABS_EVENT_GAP["5m"]
                )
                logger.info(f"  ✅ 5m scan complete for {symbol}")
            except Exception as e:
                logger.error(f"  ❌ 5m scan failed for {symbol}: {e}")

            # 2. 15m Fast15
            try:
                run_fast15_scan_for_symbol(symbol)
                logger.info(f"  ✅ 15m scan complete for {symbol}")
            except Exception as e:
                logger.error(f"  ❌ 15m scan failed for {symbol}: {e}")
            
            # 3. 1h Time-Labs
            try:
                run_1h_rally_scan_for_symbol(symbol)
                logger.info(f"  ✅ 1h scan complete for {symbol}")
            except Exception as e:
                logger.error(f"  ❌ 1h scan failed for {symbol}: {e}")
                
            # 4. 4h Time-Labs
            try:
                run_4h_rally_scan_for_symbol(symbol)
                logger.info(f"  ✅ 4h scan complete for {symbol}")
            except Exception as e:
                logger.error(f"  ❌ 4h scan failed for {symbol}: {e}")

            success_count += 1
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR processing {symbol}: {e}")
            fail_count += 1
            
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("=" * 80)
    logger.info(f"FULL SCAN COMPLETED in {duration}")
    logger.info(f"Processed: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info("=" * 80)

if __name__ == "__main__":
    run_full_scan()
