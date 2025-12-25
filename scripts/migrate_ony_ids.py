
import os
import sys
import pandas as pd
from pathlib import Path
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tezaver.core.annotations import SniperAnnotationRepository, SniperAnnotation
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
from tezaver.core import coin_cell_paths

def get_tier_code(tier_str):
    if not tier_str: return "X"
    t = str(tier_str).upper()
    if "DIAMOND" in t: return "D"
    if "GOLD" in t: return "G"
    if "SILVER" in t: return "S"
    if "BRONZE" in t: return "B"
    return "X"

def load_reference_events(symbol, timeframe):
    """Load original events to calculate Tiers for ID generation."""
    try:
        if timeframe == "15m":
            path = coin_cell_paths.get_fast15_rallies_path(symbol)
        else:
            path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
        
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        if df.empty: return None

        # Normalize time
        for col in ["event_time", "start_ts", "timestamp"]:
            if col in df.columns:
                df["event_time"] = pd.to_datetime(df[col], errors="coerce")
                break
        
        # Calculate Tier
        if 'rally_grade' in df.columns:
            # Simple normalization if column exists
            df['tier'] = df['rally_grade'].apply(lambda x: str(x).upper() if pd.notna(x) else None)
        else:
            df['tier'] = df['future_max_gain_pct'].apply(compute_tier_from_gain_pct)
            
        # Create Timestamp -> Tier Code map
        # Timestamp should be int seconds
        mapping = {}
        for _, row in df.iterrows():
            if pd.isna(row['event_time']): continue
            ts = int(row['event_time'].timestamp())
            code = get_tier_code(row['tier'])
            mapping[ts] = code
            
        return mapping
    except Exception as e:
        print(f"Error loading reference for {symbol} {timeframe}: {e}")
        return None

def migrate():
    repo_root = Path(".tezaver_matrix/foundry/annotations")
    if not repo_root.exists():
        print("No annotations found.")
        return

    print(f"Starting migration in {repo_root}...")
    
    # Iterate Symbol/Timeframe folders
    # Structure: root/SYMBOL/TIMEFRAME.json
    
    total_updated = 0
    
    for symbol_dir in repo_root.iterdir():
        if not symbol_dir.is_dir(): continue
        symbol = symbol_dir.name
        
        for tf_file in symbol_dir.glob("*.json"):
            timeframe = tf_file.stem # "15m"
            
            print(f"Processing {symbol} {timeframe}...")
            
            # 1. Load Reference Data (to get Tiers)
            tier_map = load_reference_events(symbol, timeframe)
            if not tier_map:
                print(f"  Skipping (No reference data found)")
                continue
                
            # 2. Load Annotations
            try:
                with open(tf_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"  Error reading json: {e}")
                continue
                
            updated_data = []
            changed_count = 0
            
            for item in data:
                old_id = item.get('event_id', '')
                
                # Check format. Old: {SYM}_{TF}_{TS}. New: {SYM}_{TF}_{CODE}_{TS}
                parts = old_id.split('_')
                
                # Try to extract timestamp
                # Assuming last part is TS
                ts_str = parts[-1]
                if not ts_str.isdigit():
                    # Maybe already migrated or weird format?
                    updated_data.append(item)
                    continue
                    
                ts = int(ts_str)
                
                # Check if already migrated (has 4 parts? SYM, TF, CODE, TS)
                # Old has 3 parts: ADAUSDT, 15m, 123456
                # New has 4 parts: ADAUSDT, 15m, D, 123456
                # Wait, Symbol can contain underscores? No, usually distinct.
                # Safer: Check if 2nd to last part is single char code?
                if len(parts) >= 4 and len(parts[-2]) == 1 and parts[-2] in "DGSBX":
                    # Already migrated
                    updated_data.append(item)
                    continue
                
                # Look up Tier Code
                code = tier_map.get(ts, "X") # Default to X if not found
                
                # Construct New ID
                new_id = f"{symbol}_{timeframe}_{code}_{ts}"
                
                if new_id != old_id:
                    item['event_id'] = new_id
                    changed_count += 1
                
                updated_data.append(item)
            
            if changed_count > 0:
                # Save back
                with open(tf_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_data, f, indent=2, ensure_ascii=False)
                print(f"  ✅ Updated {changed_count} records.")
                total_updated += changed_count
            else:
                print("  No changes needed.")

    print(f"\nMigration Complete. Total records updated: {total_updated}")

if __name__ == "__main__":
    migrate()
