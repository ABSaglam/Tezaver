
from tezaver.engines.tunnel_engine import TunnelEngine
from tezaver.core.config import get_turkey_now
import pandas as pd
import pytz

def check_current_status():
    print("--- 27 OCAK TUNEL KOINLERI GUNCEL DURUM (15m) ---")
    
    # 1. Use Known List (Since strict scan now rejects them)
    # The user is interested in the coins that appeared in the EARLIER scan.
    coins = [
        "AVNTUSDT", "DCRUSDT", "DODOUSDT", "GMTUSDT", 
        "HMSTRUSDT", "JTOUSDT", "METUSDT", "XPLUSDT",
        "PUMPUSDT", "INITUSDT" # Adding extras just in case
    ]
    print(f"Takip Edilen Koinler (Manuel Liste): {coins}\n")
    
    engine = TunnelEngine()
    import os

    # 2. Check CURRENT candle for each
    results = []
    
    for symbol in coins:
        try:
            # Load 15m data manually (no helper method)
            path = os.path.join(engine.cells_dir, symbol, "data", "history_15m.parquet")
            
            if not os.path.exists(path):
                print(f"Skipping {symbol}: No data file.")
                continue

            df = pd.read_parquet(path)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') # Parquet usually stores ms int or datetime directly
            
            # Simple check if ms conversion needed
            if df['timestamp'].iloc[-1].year < 2000:
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Get latest candle
            last_candle = df.iloc[-1]
            last_time = last_candle['timestamp'].tz_localize('UTC').astimezone(pytz.timezone('Europe/Istanbul'))

            
            # Simple metrics
            close = last_candle['close']
            open_ = last_candle['open']
            p_change = ((close - open_) / open_) * 100
            
            # Add to list
            results.append({
                "SYM": symbol,
                "LAST_TIME": last_time.strftime('%H:%M'),
                "PRICE": close,
                "15m_CHG": f"{p_change:+.2f}%",
                "VOL": f"{last_candle['volume']:.0f}"
            })
            
        except Exception as e:
            print(f"Error checking {symbol}: {e}")
            
    # Print Table
    if results:
         res_df = pd.DataFrame(results)
         print(res_df.to_string(index=False))

if __name__ == "__main__":
    check_current_status()
