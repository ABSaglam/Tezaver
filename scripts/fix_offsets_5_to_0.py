
import os
import sys
import json
from pathlib import Path

def fix_offsets():
    repo_root = Path(".tezaver_matrix/foundry/annotations")
    if not repo_root.exists():
        print("No annotations found.")
        return

    print(f"Starting Offset Fix (5 -> 0) in {repo_root}...")
    
    total_updated = 0
    
    for symbol_dir in repo_root.iterdir():
        if not symbol_dir.is_dir(): continue
        
        for tf_file in symbol_dir.glob("*.json"):
            try:
                with open(tf_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Skipping {tf_file}: {e}")
                continue
                
            updated_data = []
            changed_count = 0
            
            for item in data:
                # If offset is 5, reset to 0
                current_off = item.get('entry_bar_offset', 0)
                if current_off == 5:
                    item['entry_bar_offset'] = 0
                    changed_count += 1
                
                updated_data.append(item)
            
            if changed_count > 0:
                with open(tf_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_data, f, indent=2, ensure_ascii=False)
                # print(f"  Fixed {changed_count} records in {tf_file.name}")
                total_updated += changed_count

    print(f"\nOffset Fix Complete. Total records updated: {total_updated}")

if __name__ == "__main__":
    fix_offsets()
