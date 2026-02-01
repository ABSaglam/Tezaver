
import os
import time
from tezaver.core.config import COIN_CELLS_DIR

def debug_audit():
    print(f"Checking directory: {COIN_CELLS_DIR}")
    
    if not os.path.exists(COIN_CELLS_DIR):
        print("Directory does not exist!")
        return

    files = [f for f in os.listdir(COIN_CELLS_DIR) if f.endswith('_key.json')]
    print(f"Found {len(files)} key files.")
    
    if files:
        # Check the first file
        first_file = files[0]
        path = os.path.join(COIN_CELLS_DIR, first_file)
        mtime = os.path.getmtime(path)
        print(f"Sample file: {first_file}")
        print(f"Types: mtime={type(mtime)}, current={type(time.time())}")
        print(f"Modification Time: {mtime} -> {time.ctime(mtime)}")
        print(f"Current Time: {time.time()} -> {time.ctime(time.time())}")
        print(f"Difference (hours): {(time.time() - mtime) / 3600:.2f}")

if __name__ == '__main__':
    debug_audit()
