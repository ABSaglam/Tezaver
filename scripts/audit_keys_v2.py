
import os
import time
import json

# Hardcoded correct path based on exploration
KEYS_DIR = '/Users/alisaglam/TezaverMac/data/golden_keys'

def audit_modified_keys():
    # Check for files modified in the last 48 hours (to cover previous session)
    recent_limit = time.time() - (48 * 3600)
    
    modified_files = []
    
    if not os.path.exists(KEYS_DIR):
        print(f"Directory not found: {KEYS_DIR}")
        return

    all_files = os.listdir(KEYS_DIR)
    print(f"Total files in directory: {len(all_files)}")

    for filename in all_files:
        if filename.endswith('_key.json'):
            path = os.path.join(KEYS_DIR, filename)
            try:
                mtime = os.path.getmtime(path)
                if mtime > recent_limit:
                    modified_files.append((filename, mtime))
            except:
                pass
                
    print(f"Files modified in last 48 hours: {len(modified_files)}")
    
    # List top 5 latest
    modified_files.sort(key=lambda x: x[1], reverse=True)
    for f, t in modified_files[:5]:
        print(f"{f} - {time.ctime(t)}")
        
    # Inspect content of the first modified file
    if modified_files:
        latest_file = modified_files[0][0]
        latest_path = os.path.join(KEYS_DIR, latest_file)
        with open(latest_path, 'r') as f:
            data = json.load(f)
        print(f"\nContent of {latest_file}:")
        print(json.dumps(data, indent=2))

if __name__ == '__main__':
    audit_modified_keys()
