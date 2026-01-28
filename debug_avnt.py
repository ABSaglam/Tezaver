
from tezaver.engines.tunnel_engine import TunnelEngine
import pandas as pd

# Force debug
pd.set_option('display.max_rows', 100)

def debug_avnt():
    print("--- DEBUG AVNTUSDT ---")
    engine = TunnelEngine()
    
    # 1. Load Data
    try:
        df = engine._get_data_df("AVNTUSDT")
        print(f"Data Loaded. Shape: {df.shape}")
        print(f"Last Candle: {df.index[-1]}")
    except Exception as e:
        print(f"Data Load Failed: {e}")
        return

    # 2. Check Day Slice
    scan_date = "2026-01-27"
    day_df = df[df.index.strftime('%Y-%m-%d') == scan_date]
    print(f"Jan 27 Data Count: {len(day_df)} rows")
    
    if day_df.empty:
        print("NO DATA FOR JAN 27!")
        return

    # 3. Check Metrics at 01:00 (Where signal was before)
    # The timezone handling in engine might use UTC or TR time.
    # scan_tunnel_day slices by strftime inside.
    
    # Run scan for just this coin
    print("\nRunning Scan for AVNTUSDT...")
    triggers = engine._find_triggers(df, scan_date)
    print(f"Triggers Found: {len(triggers)}")
    
    for t in triggers:
        print(f"Time: {t['time']} | Trend: {t['trend_icon']} | Angle: {t['angle_val']}")

if __name__ == "__main__":
    debug_avnt()
