#!/usr/bin/env python3
"""
BTCUSDT 15m History Data Refresher
===================================
Downloads latest 1000 bars of BTCUSDT 15m data from Binance and saves to coin_cells.
"""

import pandas as pd
from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths

def refresh_btc_15m():
    print("📡 Connecting to Binance...")
    client = BinanceClient()
    
    symbol = 'BTC/USDT'  # CCXT format
    timeframe = '15m'
    
    print(f"📥 Downloading {symbol} {timeframe} data (last 1000 bars)...")
    records = client.fetch_ohlcv(symbol, timeframe, limit=1000)
    
    if not records:
        print("❌ No data received!")
        return
    
    # Convert to DataFrame
    data = []
    for rec in records:
        data.append({
            'ts': rec.timestamp // 1000,  # Convert ms to seconds (to match existing format)
            'open': rec.open,
            'high': rec.high,
            'low': rec.low,
            'close': rec.close,
            'volume': rec.volume
        })
    
    df = pd.DataFrame(data)
    
    # Save to coin_cells
    output_path = coin_cell_paths.get_history_file('BTCUSDT', '15m')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(output_path, index=False)
    
    print(f"✅ Saved {len(df)} bars to: {output_path}")
    print(f"📊 Time range: {pd.to_datetime(df['ts'].min(), unit='s')} → {pd.to_datetime(df['ts'].max(), unit='s')}")
    print(f"💾 File size: {output_path.stat().st_size / 1024:.1f} KB")

if __name__ == "__main__":
    refresh_btc_15m()
