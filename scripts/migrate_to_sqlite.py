"""
Migration Script: Parquet/JSON -> SQLite
========================================
Migrates existing data from the "File System Era" to the "Unified Database Era".

Flow:
1. Scan all 15m/1h/4h Parquet files.
2. Insert them as 'raw_data' rows in SQLite.
3. Scan all Annotation JSON files.
4. Update corresponding rows with 'rev_data' in SQLite.
5. If Annotation exists but Raw is missing (orphan), create row.
"""

import sys
import pandas as pd
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.tezaver.core.rally_store import RallyStore
from src.tezaver.core import coin_cell_paths
from src.tezaver.core.annotations import SniperAnnotationRepository

def migrate():
    print("🚀 Starting Migration to SQLite...")
    store = RallyStore()
    
    # 1. Migrate RAW Data (Parquet)
    # -----------------------------
    lib_root = coin_cell_paths.get_library_root()
    
    # A. Fast15 (15m)
    print("\n📦 Migrating 15m Rallies...")
    fast15_dir = lib_root / "fast15_rallies"
    if fast15_dir.exists():
        for sym_dir in fast15_dir.iterdir():
            if sym_dir.is_dir():
                parquet_path = sym_dir / "fast15_rallies.parquet"
                if parquet_path.exists():
                    try:
                        df = pd.read_parquet(parquet_path)
                        count = 0
                        for _, row in df.iterrows():
                            # Convert to dict
                            data = row.to_dict()
                            # Ensure ID
                            eid = str(data.get('event_id', ''))
                            if not eid: continue
                            
                            data['timeframe'] = '15m' # Explicitly set
                            
                            # Upsert
                            store.upsert_rally(eid, data, layer='raw')
                            count += 1
                        print(f"   ✓ {sym_dir.name}: {count} events")
                    except Exception as e:
                        print(f"   ❌ {sym_dir.name}: Error {e}")

    # B. TimeLabs (1h / 4h)
    print("\n📦 Migrating TimeLabs (1h/4h)...")
    time_labs_dir = lib_root / "time_labs"
    if time_labs_dir.exists():
        for tf_dir in time_labs_dir.iterdir(): # 1h, 4h
            if tf_dir.is_dir():
                tf = tf_dir.name
                for sym_dir in tf_dir.iterdir():
                    if sym_dir.is_dir():
                        parquet_path = sym_dir / f"rallies_{tf}.parquet"
                        if parquet_path.exists():
                            try:
                                df = pd.read_parquet(parquet_path)
                                count = 0
                                for _, row in df.iterrows():
                                    data = row.to_dict()
                                    eid = str(data.get('event_id', ''))
                                    if not eid: continue
                                    
                                    data['timeframe'] = tf
                                    store.upsert_rally(eid, data, layer='raw')
                                    count += 1
                                print(f"   ✓ {sym_dir.name} ({tf}): {count} events")
                            except Exception as e:
                                print(f"   ❌ {sym_dir.name} ({tf}): Error {e}")

    # 2. Migrate ANNOTATIONS (JSON)
    # -----------------------------
    print("\n📝 Migrating Annotations...")
    repo = SniperAnnotationRepository()
    ann_root = Path(repo.root_dir)
    
    if ann_root.exists():
        for sym_dir in ann_root.iterdir():
            if sym_dir.is_dir():
                # Each file is {timeframe}.json containing list of annotations
                for json_file in sym_dir.glob("*.json"):
                    tf = json_file.stem # "15m", "1h"
                    try:
                        with open(json_file, 'r') as f:
                            anns = json.load(f)
                            
                        count = 0
                        for ann_data in anns:
                            eid = ann_data.get('event_id')
                            if not eid: continue
                            
                            # Clean up
                            ann_data['symbol'] = sym_dir.name
                            ann_data['timeframe'] = tf
                            
                            # MOLDER DATA EXTRACTION
                            # If archetype exists, we should also populate molder layer?
                            # For now, let's put everything in 'rev_data' as per current structure.
                            # BUT, ideal architecture separates them.
                            # Let's populate 'rev_data' with everything for now since Repo stores it together.
                            
                            store.upsert_rally(eid, ann_data, layer='rev')
                            
                            # If Archetype is present, also populate molder layer
                            if ann_data.get('archetype'):
                                molder_data = {
                                    'archetype': ann_data['archetype'],
                                    'mapped_from_legacy': True
                                }
                                store.upsert_rally(eid, molder_data, layer='molder')
                                
                            count += 1
                        print(f"   ✓ {sym_dir.name} ({tf}): {count} annotations")
                    except Exception as e:
                        print(f"   ❌ {json_file}: Error {e}")

    print("\n✅ Migration Complete.")

if __name__ == "__main__":
    migrate()
