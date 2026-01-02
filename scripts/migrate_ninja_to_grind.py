#!/usr/bin/env python3
"""
Migration Script: NINJA → GRIND
================================

Converts all NINJA-labeled rallies to GRIND archetype.
Updates both molder_data and rev_data layers.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tezaver.core.rally_store import RallyStore
import pandas as pd
import sqlite3
import json

def migrate_ninja_to_grind():
    """Migrate all NINJA rallies to GRIND."""
    store = RallyStore()
    
    # Connect to database directly
    db_path = store.db_path
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query for NINJA rallies
    query = """
        SELECT id, molder_data, rev_data 
        FROM rallies 
        WHERE molder_data LIKE '%NINJA%' OR rev_data LIKE '%NINJA%'
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    ninja_count = 0
    updated_count = 0
    
    print("🔍 Scanning for NINJA rallies...")
    print(f"   Found {len(rows)} potential NINJA rallies\n")
    
    import json
    
    for row in rows:
        event_id = row[0]
        molder_json = row[1]
        rev_json = row[2]
        
        # Parse JSON  
        molder_data = json.loads(molder_json) if molder_json else {}
        rev_data = json.loads(rev_json) if rev_json else {}
        
        molder_arch = molder_data.get('archetype')
        rev_arch = rev_data.get('archetype')
        
        needs_update = False
        
        # Update molder_data if NINJA
        if molder_arch == 'NINJA':
            ninja_count += 1
            molder_data['archetype'] = 'GRIND'
            molder_data['migrated_from'] = 'NINJA'
            molder_data['migration_date'] = str(pd.Timestamp.now())
            needs_update = True
            print(f"  📝 Molder: {event_id} - NINJA → GRIND")
        
        # Update rev_data if NINJA
        if rev_arch == 'NINJA':
            rev_data['archetype'] = 'GRIND'
            rev_data['migrated_from'] = 'NINJA'
            rev_data['migration_date'] = str(pd.Timestamp.now())
            needs_update = True
            print(f"  📝 Rev: {event_id} - NINJA → GRIND")
        
        # Save if updated
        if needs_update:
            if molder_arch == 'NINJA':
                store.upsert_rally(event_id, molder_data, layer='molder')
            if rev_arch == 'NINJA':
                store.upsert_rally(event_id, rev_data, layer='rev')
            updated_count += 1
    
    print(f"\n✅ Migration complete!")
    print(f"   NINJA rallies found: {ninja_count}")
    print(f"   Rallies updated: {updated_count}")
    
    return ninja_count, updated_count

if __name__ == "__main__":
    migrate_ninja_to_grind()
