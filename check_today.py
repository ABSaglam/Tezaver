
from tezaver.engines.tunnel_engine import TunnelEngine
import pandas as pd
from datetime import datetime

# Set pandas display options
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

def scan_today():
    engine = TunnelEngine()
    today_str = "2026-01-28"
    print(f"Scanning for {today_str}...")
    
    try:
        df = engine.scan_tunnel_day(today_str)
        if not df.empty:
            print(f"FOUND {len(df)} SIGNALS:")
            # Filter for early triggers if possible, or just show all
            print(df[['SYM', 'TIME', 'P', 'V100']].to_string())
        else:
            print("No signals found for today yet.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scan_today()
