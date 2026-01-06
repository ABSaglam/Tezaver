
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import time

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.data.binance_client import BinanceClient
from tezaver.data.history_service import save_history
from tezaver.data.run_full_history_sync import fetch_full_history
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def recover_data():
    client = BinanceClient()
    start_dt = datetime.now() - timedelta(days=730)
    start_ts = int(start_dt.timestamp() * 1000)
    
    # 1. Recover 5m
    missing_5m = ['VETUSDT']
    for sym in missing_5m:
        print(f"Recovering {sym} 5m...")
        try:
            df = fetch_full_history(client, sym, "5m", start_ts)
            if not df.empty:
                save_history(sym, "5m", df)
                print(f"✅ Saved {len(df)} bars for {sym} 5m")
        except Exception as e:
            print(f"❌ Error {sym} 5m: {e}")

    # 2. Recover 15m
    missing_15m = ['CYBERUSDT', 'DEXEUSDT', 'DFUSDT']
    for sym in missing_15m:
        print(f"Recovering {sym} 15m...")
        try:
            df = fetch_full_history(client, sym, "15m", start_ts)
            if not df.empty:
                save_history(sym, "15m", df)
                print(f"✅ Saved {len(df)} bars for {sym} 15m")
        except Exception as e:
            print(f"❌ Error {sym} 15m: {e}")

if __name__ == "__main__":
    recover_data()
