"""
Fix archetype mapping - use direct ID match from rally_archetypes.csv
"""

import sys
import os
import pandas as pd
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

print("=" * 60)
print("🔧 Ralli Arketiplerini Doğrudan Güncelle")
print("=" * 60)

# Load rallies and archetypes
conn = sqlite3.connect(DB_PATH)

# Get all DSG rallies
df_rallies = pd.read_sql_query(
    "SELECT id, symbol, tier, raw_data FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER') ORDER BY symbol, event_time", 
    conn
)

# Load archetype file (has same order as original query)
arch_file = coin_cell_paths.get_library_root() / "rally_archetypes.csv"
df_arch = pd.read_csv(arch_file)

print(f"Rallies: {len(df_rallies)}")
print(f"Archetypes: {len(df_arch)}")

if len(df_rallies) == len(df_arch):
    # Same length - direct mapping by index
    df_rallies['archetype'] = df_arch['archetype'].values
    
    # Update database
    cursor = conn.cursor()
    for i, row in df_rallies.iterrows():
        cursor.execute("UPDATE rallies SET archetype = ? WHERE id = ?", (row['archetype'], row['id']))
        if (i + 1) % 10000 == 0:
            print(f"İlerleme: {i+1}/{len(df_rallies)}")
    
    conn.commit()
    print("✅ Güncelleme tamamlandı")
else:
    print("❌ Satır sayısı uyuşmuyor")

# Verify
result = pd.read_sql_query(
    "SELECT tier, archetype, COUNT(*) as count FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER') GROUP BY tier, archetype ORDER BY tier, count DESC", 
    conn
)
print("\n📊 Arketip Dağılımı (Doğrulanmış):")
for tier in ['DIAMOND', 'GOLD', 'SILVER']:
    tier_data = result[result['tier'] == tier]
    print(f"\n{tier}:")
    for _, r in tier_data.iterrows():
        print(f"   {r['archetype']:12s}: {r['count']:5d}")

conn.close()
