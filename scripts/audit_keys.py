
import os
import time
from tezaver.core.config import COIN_CELLS_DIR

def audit_modified_keys():
    # Check for files modified in the last 24 hours
    recent_limit = time.time() - (24 * 3600)
    
    modified_files = []
    
    try:
        files = os.listdir(COIN_CELLS_DIR)
    except Exception as e:
        print(f"Error accessing directory: {e}")
        return

    for filename in files:
        if filename.endswith('_key.json'):
            path = os.path.join(COIN_CELLS_DIR, filename)
            try:
                mtime = os.path.getmtime(path)
                if mtime > recent_limit:
                    modified_files.append((filename, mtime))
            except:
                pass
                
    print(f"Total files in directory: {len(files)}")
    print(f"Files modified in last 24 hours: {len(modified_files)}")
    
    # List top 20 latest
    modified_files.sort(key=lambda x: x[1], reverse=True)
    for f, t in modified_files[:20]:
        print(f"{f} - {time.ctime(t)}")

if __name__ == '__main__':
    audit_modified_keys()
