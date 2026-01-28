import sys
import os
import json
import subprocess
import time

def run_mass_update_2026():
    whitelist_path = "data/spot_whitelist_437.json"
    
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist not found.")
        return

    with open(whitelist_path, "r") as f:
        all_coins = json.load(f)

    print(f"🏭 MASS UPDATE FOR 2026 DATA STARTED")
    print(f"   Target List: {len(all_coins)} coins")
    
    # Setup Environment
    env = os.environ.copy()
    cwd = os.getcwd()
    src_path = os.path.join(cwd, "src")
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{existing_pp}:{cwd}:{src_path}" if existing_pp else f"{cwd}:{src_path}"
    
    processed_count = 0
    total = len(all_coins)
    
    for symbol in all_coins:
        print(f"\n🚀 Processing [{processed_count+1}/{total}] {symbol}...")
        
        try:
            # 1. Forge (Updates Golden Key with latest data)
            forge_proc = subprocess.run(
                [sys.executable, "scripts/forge_golden_key.py", symbol],
                capture_output=True, text=True, timeout=120, env=env
            )
            
            if "🏆 GOLDEN KEY FORGED" in forge_proc.stdout:
                # 2. Report (Generates Detailed List Artifact)
                report_proc = subprocess.run(
                    [sys.executable, "scripts/report_v4_details.py", symbol],
                    capture_output=True, text=True, timeout=30, env=env
                )
                
                if "✅ Detailed report saved" in report_proc.stdout:
                    print(f"   ✅ SUCCESS: {symbol}")
                else:
                    print(f"   ⚠️ Report failed for {symbol}")
                    # print(report_proc.stdout)
            elif "❌ Missing data" in forge_proc.stdout:
                print(f"   ❌ SKIP: {symbol} (Missing Data)")
            else:
                print(f"   ❌ FAIL: {symbol} (Forge Failed)")
                # print(forge_proc.stdout)
                
        except Exception as e:
            print(f"   🔥 CRASH: {symbol} - {e}")
            
        processed_count += 1

    print("\n🏁 Mass Update Complete.")

if __name__ == "__main__":
    run_mass_update_2026()
