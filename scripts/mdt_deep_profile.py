"""
MDTUSDT Deep Profile
====================
Analyzes MDT's rally history and characteristics.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

def main():
    symbol = 'MDTUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    # Rally counts
    cursor.execute("SELECT tier, COUNT(*) FROM rallies WHERE symbol = ? GROUP BY tier", (symbol,))
    tiers = dict(cursor.fetchall())
    
    print("="*80)
    print(f"📊 MDTUSDT DEEP PROFILE")
    print("="*80)
    print(f"\n💎 Diamonds: {tiers.get('DIAMOND', 0)}")
    print(f"🥇 Golds:    {tiers.get('GOLD', 0)}")
    print(f"🥈 Silvers:  {tiers.get('SILVER', 0)}")
    print(f"🔥 TOTAL DG: {tiers.get('DIAMOND', 0) + tiers.get('GOLD', 0)}")
    
    # Get all DG rallies
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
    rallies = cursor.fetchall()
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    print(f"\n📅 Data Range: {df_1d['datetime'].min().date()} to {df_1d['datetime'].max().date()}")
    print(f"📈 Total Trading Days: {len(df_1d)}")
    
    # Rally distribution by year
    rally_years = {}
    for raw_data, tier in rallies:
        raw = json.loads(raw_data)
        year = pd.to_datetime(raw['start_time']).year
        rally_years[year] = rally_years.get(year, 0) + 1
    
    print("\n📆 Rally Distribution by Year:")
    for year in sorted(rally_years.keys()):
        print(f"  {year}: {rally_years[year]} DG rallies")
    
    conn.close()

if __name__ == "__main__":
    main()
