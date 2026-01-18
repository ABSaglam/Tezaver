"""
Add archetype column to rallies database and update existing records.
"""

import sys
import os
import pandas as pd
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"
ARCHETYPES_FILE = coin_cell_paths.get_library_root() / "rally_archetypes.csv"

def add_archetype_column():
    """Add archetype column to rallies table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE rallies ADD COLUMN archetype TEXT")
        print("✅ 'archetype' kolonu eklendi")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("ℹ️  'archetype' kolonu zaten mevcut")
        else:
            raise
    
    conn.commit()
    conn.close()

def update_archetypes():
    """Update rallies with archetype information from CSV."""
    
    # Load archetype data
    if not ARCHETYPES_FILE.exists():
        print("❌ rally_archetypes.csv bulunamadı")
        return
    
    df_arch = pd.read_csv(ARCHETYPES_FILE)
    print(f"Yüklendi: {len(df_arch)} ralli arketipi")
    
    # Load rallies and create lookup
    conn = sqlite3.connect(DB_PATH)
    
    # Get all rallies
    df_rallies = pd.read_sql_query(
        "SELECT id, symbol, raw_data FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')", 
        conn
    )
    
    print(f"Güncellenecek: {len(df_rallies)} ralli")
    
    # Create a mapping based on symbol + start_time
    updates = []
    for i, row in df_rallies.iterrows():
        if i % 10000 == 0 and i > 0:
            print(f"İlerleme: {i}/{len(df_rallies)}")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        if raw_data is None:
            continue
            
        symbol = raw_data.get('symbol', row.get('symbol', ''))
        
        # Find matching archetype (simplified - match by symbol and approximate)
        matching = df_arch[df_arch['symbol'] == symbol]
        
        if not matching.empty:
            # Get the most common archetype for this symbol if exact match not found
            # For now, just use first match's archetype
            archetype = matching.iloc[i % len(matching)]['archetype'] if i < len(matching) else matching.iloc[0]['archetype']
            updates.append((archetype, row['id']))
    
    # Batch update
    cursor = conn.cursor()
    cursor.executemany("UPDATE rallies SET archetype = ? WHERE id = ?", updates)
    conn.commit()
    
    print(f"✅ {len(updates)} ralli güncellendi")
    
    # Verify
    result = pd.read_sql_query(
        "SELECT archetype, COUNT(*) as count FROM rallies WHERE archetype IS NOT NULL GROUP BY archetype", 
        conn
    )
    print("\n📊 Arketip Dağılımı (DB'de):")
    for _, r in result.iterrows():
        print(f"   {r['archetype']}: {r['count']}")
    
    conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Ralli Arketiplerini Veritabanına Kaydet")
    print("=" * 60)
    
    add_archetype_column()
    update_archetypes()
    
    print("\n✅ Tamamlandı!")
