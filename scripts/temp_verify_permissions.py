import pandas as pd
import json
import os
import sys

def check_permissions():
    whitelist_path = "data/spot_whitelist_437.json"
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist not found.")
        return

    with open(whitelist_path, "r") as f:
        all_coins = json.load(f)
        
    # Dates to check (The permission is generated ON this date for the NEXT day, 
    # OR generated ON previous day for THIS date. 
    # User asked for "Last Night's Permissions" for 26 and 27.
    # So we check the DNA state at the start of Jan 26 and Jan 27.
    
    target_dates = [pd.Timestamp("2026-01-26"), pd.Timestamp("2026-01-27")]
    
    results = {
        "2026-01-26": [],
        "2026-01-27": []
    }
    
    print(f"🔍 Checking Golden Key Permissions for {len(all_coins)} coins...")
    
    for symbol in all_coins:
        try:
            # Load Golden Key to get ALLOWED DNA list
            key_path = f"data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path):
                continue
                
            with open(key_path, "r") as f:
                key_data = json.load(f)
            
            allowed_dna = set(key_data.get('golden_dna_list', []))
            if not allowed_dna:
                continue

            # Load Daily Data to compute DNA for specific days
            df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
            df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
            df_d.set_index('dt', inplace=True)
            df_d.sort_index(inplace=True)
            
            # Helper to calculate DNA (Simplified from production logic)
            # We need to replicate the 'get_profile' logic roughly or just trust the outcome if stored?
            # Stored DNA is better if available, but usually computed on fly.
            # Let's use a simplified DNA checker from the audit script logic.
            
            # Actually, to be 100% accurate, we should import the EXACT function.
            # But for now, let's assume if the coin *would* have passed the check.
            
            for target_date in target_dates:
                # Permission for target_date is based on PREVIOUS day's close.
                # So we look at the row for target_date - 1 day ?? 
                # No, typically 'Daily Close' of Jan 25 determines permission for Jan 26 trading day.
                
                check_date = target_date - pd.Timedelta(days=1)
                
                # Check if we have data
                # We need to compute DNA for 'check_date'
                # ... (Implementing simplified DNA logic here would be huge duplication)
                # Alternative: Just list coins that HAVE valid data and their DNA matches?
                pass

        except Exception as e:
            pass

    # PLAN B: Since DNA logic is complex (RSI, Squeeze, Harmony etc.), 
    # listing *all* permissions requires running the full engine.
    # Instead, I will parse the 'refined_global_report_v16.md' output? 
    # No, that only shows SIGNALS. The user wants PERMISSIONS (even if no signal).
    
    print("⚠️ To get exact permissions, I must run the DNA profiler. Switching to a smarter method.")

if __name__ == "__main__":
    check_permissions()
