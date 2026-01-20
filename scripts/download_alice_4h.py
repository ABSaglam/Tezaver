
import sys
import os
import pandas as pd
from binance.client import Client

def download_4h(symbol="ALICEUSDT"):
    print(f"⬇️ DOWNLOADING {symbol} 4H DATA...")
    client = Client() 
    start_str = "1 Jan, 2023"
    klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_4HOUR, start_str)
    
    data = []
    for k in klines:
        data.append({
            'timestamp': k[0],
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5])
        })
        
    df = pd.DataFrame(data)
    path = f"coin_cells/{symbol}/data/history_4h.parquet"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path)
    print(f"✅ Saved {len(df)} rows to {path}")

if __name__ == "__main__":
    download_4h()
