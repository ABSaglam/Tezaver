import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from tezaver.core import coin_cell_paths, config
from tezaver.core.rally_store import RallyStore

def audit_data():
    store = RallyStore()
    test_coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "ARKUSDT"]
    
    print("--- DATA AUDIT REPORT ---")
    for symbol in test_coins:
        print(f"\n🔍 Auditing {symbol}...")
        
        # 1. Parquet File Checks
        missing_files = []
        for tf in ['15m', '4h', '1d']:
            p = coin_cell_paths.get_history_file(symbol, tf)
            f = coin_cell_paths.get_coin_data_dir(symbol) / f"features_{tf}.parquet"
            if not p.exists(): missing_files.append(f"History-{tf}")
            if not f.exists(): missing_files.append(f"Features-{tf}")
            
        if missing_files:
            print(f"  ❌ Missing: {', '.join(missing_files)}")
        else:
            print(f"  ✅ Parquet files for 15m, 4h, 1d exist.")
            
        # 2. Timeframe Comparison (Sample)
        try:
            df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
            df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h'))
            
            last_1d = df_1d['datetime'].max()
            last_4h = df_4h['datetime'].max()
            
            print(f"  🕒 Last 1d bar: {last_1d}")
            print(f"  🕒 Last 4h bar: {last_4h}")
            
            diff = abs((last_1d - last_4h).total_seconds())
            if diff < 24 * 3600:
                print(f"  ✅ Timeframes are aligned within 24 hours.")
            else:
                print(f"  ⚠️ Warning: Timeframes might be misaligned (>24h diff).")
        except Exception as e:
            print(f"  ❌ Timeframe check failed: {e}")

        # 3. RallyStore Retrieval
        try:
            rallies = store.list_rallies(symbol=symbol, timeframe='15m')
            print(f"  📈 RallyStore: Found {len(rallies)} rallies for 15m.")
            if len(rallies) > 0:
                print(f"  ✅ Rally retrieval working.")
            else:
                print(f"  ⚠️ No rallies in store yet (Expected if Phase 3 not started for this coin).")
        except Exception as e:
            print(f"  ❌ RallyStore check failed: {e}")

if __name__ == "__main__":
    audit_data()
