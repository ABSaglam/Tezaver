import sys
import os
import json
import subprocess
import time

def run_mass_production():
    whitelist_path = "data/spot_whitelist_437.json"
    status_path = "data/production_v4_status.json"
    
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist not found.")
        return

    with open(whitelist_path, "r") as f:
        all_coins = json.load(f)

    # Load or init status
    status = {}
    if os.path.exists(status_path):
        with open(status_path, "r") as f:
            status = json.load(f)
            
    print(f"🏭 AYAŞ TÜNELİ v4 MASS PRODUCTION")
    print(f"   Target List: {len(all_coins)} coins")
    print(f"   Completed: {sum(1 for v in status.values() if v == 'SUCCESS')} coins")
    
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, help="Mode e.g. G_SERIES_ONLY")
    args = parser.parse_args()
    
    target_letter = None
    if args.mode and "_SERIES_ONLY" in args.mode:
        target_letter = args.mode.split("_")[0]
        print(f"🎯 MODE ACTIVE: {target_letter} Series Only")

    # Filter loop
    processed_count = 0
    limit = 20
    
    for symbol in all_coins:
        # 1. Letter Filter
        if target_letter:
            if not symbol.startswith(target_letter):
                continue
                
        # 2. Status Check
        if status.get(symbol) == "SUCCESS":
            continue
            
        print(f"\n🚀 Processing [{processed_count+1}/{limit}] {symbol}...")
        
        try:
            # 1. Forge
            forge_proc = subprocess.run(
                [sys.executable, "scripts/forge_golden_key.py", symbol],
                capture_output=True, text=True, timeout=120
            )
            
            if "🏆 GOLDEN KEY FORGED" in forge_proc.stdout:
                # 2. Report
                report_proc = subprocess.run(
                    [sys.executable, "scripts/report_v4_details.py", symbol],
                    capture_output=True, text=True, timeout=30
                )
                
                if "✅ Detailed report saved" in report_proc.stdout:
                    print(f"   ✅ SUCCESS: {symbol}")
                    status[symbol] = "SUCCESS"
                else:
                    print(f"   ⚠️ Report failed for {symbol}")
                    status[symbol] = "REPORT_FAILED"
            elif "❌ Missing data" in forge_proc.stdout:
                print(f"   ❌ SKIP: {symbol} (Missing Data)")
                status[symbol] = "MISSING_DATA"
            else:
                print(f"   ❌ FAIL: {symbol}")
                status[symbol] = "FORGE_FAILED"
                # print(forge_proc.stdout)
                
        except Exception as e:
            print(f"   🔥 CRASH: {symbol} - {e}")
            status[symbol] = f"CRASHED: {e}"
            
        # Update status file after each coin
        with open(status_path, "w") as f:
            json.dump(status, f, indent=2)
            
        processed_count += 1
        if processed_count >= limit:
            break

    print("\n🏁 Batch complete.")

if __name__ == "__main__":
    run_mass_production()
