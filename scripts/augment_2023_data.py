"""
Augment 2023 Data
==================
Downloads 2023 historical data for all coins and merges with existing data.
Timeframes: 1w, 1d, 4h, 1h, 15m
Invokes download_spot_data.py for each.
"""

import sys
import os
import subprocess

def augment_data():
    print("=" * 80)
    print("📦 2023 DATA AUGMENTATION STARTED")
    print("=" * 80)
    
    # Order: Fastest to slowest
    timeframes = ['1w', '1d', '4h', '1h', '15m']
    year = 2023
    
    script_path = os.path.join(os.path.dirname(__file__), "download_spot_data.py")
    
    for tf in timeframes:
        print(f"\nProcessing Timeframe: {tf}...")
        cmd = [sys.executable, script_path, "--tf", tf, "--year", str(year)]
        
        try:
            # Run synchronously
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed for {tf}: {e}")
            
    print("\n" + "=" * 80)
    print("✅ 2023 AUGMENTATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    augment_data()
