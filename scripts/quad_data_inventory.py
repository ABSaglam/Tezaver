"""
Quadratic Data Inventory
========================
Profiles the history of SYN, OM, MDT, RAY.
Counts Diamonds, Golds, and Silvers.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3

def main():
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()

    print("="*80)
    print("📊 QUADRATIC CLUSTER INVENTORY (SYN, OM, MDT, RAY)")
    print("="*80)

    for symbol in symbols:
        cursor.execute("SELECT tier, COUNT(*) FROM rallies WHERE symbol = ? GROUP BY tier", (symbol,))
        tiers = dict(cursor.fetchall())
        
        d = tiers.get('DIAMOND', 0)
        g = tiers.get('GOLD', 0)
        s = tiers.get('SILVER', 0)
        
        print(f"\n🪙 {symbol}:")
        print(f"  💎 Diamonds: {d}")
        print(f"  🥇 Golds:    {g}")
        print(f"  🥈 Silvers:  {s}")
        print(f"  🔥 TOTAL DG: {d + g}")

    conn.close()

if __name__ == "__main__":
    main()
