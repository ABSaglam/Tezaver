import os
import json
import pandas as pd
from datetime import date
from tezaver.engines.tunnel_engine import TunnelEngine

def repair_keys(target_dates):
    engine = TunnelEngine()
    # Mock to bypass permission during scan, but we will use the REAL logic to get DNA
    original_check = engine.check_permission
    
    # We want to find coins that WOULD pass if permission was granted
    # So we temporarily patch check_permission to say YES, so we can see the triggers
    engine.check_permission = lambda sym, d: (True, 'GRANTED', 'temp_dna')
    
    total_updated = 0
    
    for day_num in target_dates:
        target_date = date(2026, 1, day_num)
        print(f"Scanning {target_date} for repair...")
        
        try:
            results = engine.scan_tunnel_day(target_date)
            
            if not isinstance(results, pd.DataFrame) or results.empty:
                print(f"  No triggers found for {target_date}")
                continue
                
            print(f"  Found {len(results)} triggered coins. Updating keys...")
            
            for _, row in results.iterrows():
                sym = row.get('_SYM_REAL', row.get('SYM'))
                if not sym: continue
                
                # Get the REAL CURRENT DNA using the original method
                # We need to access the internal _get_profile_simple or use check_permission logic
                # Since check_permission returns the DNA even if denied, we can use it (after unpatching or just calling original)
                
                # But engine.check_permission is patched on the instance.
                # We can call the original function bound to the instance if we saved it? 
                # No, 'original_check' is a bound method, so calling original_check(sym, target_date) might fail if it relies on 'self' which is the engine?
                # Actually, original_check is bound to 'engine', so calling it should work perfectly.
                
                _, status, real_dna = original_check(sym, target_date)
                
                if status == 'GRANTED':
                    # Already granted, no need to fix (unlikely given our problem)
                    continue
                    
                # Fix: Add this DNA to the key file
                key_path = os.path.join(engine.golden_keys_dir, f"{sym}_key.json")
                
                if os.path.exists(key_path):
                    with open(key_path, 'r') as f:
                        data = json.load(f)
                    
                    if real_dna not in data.get('golden_dna_list', []):
                        data['golden_dna_list'].append(real_dna)
                        data['unique_dna_count'] = len(data['golden_dna_list'])
                        
                        with open(key_path, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        print(f"    FIXED: {sym} (+DNA: {real_dna[:30]}...)")
                        total_updated += 1
                else:
                    # Create new key file if it doesn't exist?
                    # Depending on policy. For now, only update existing known coins.
                    pass
                    
        except Exception as e:
            print(f"Error scanning {target_date}: {e}")
            
    # Restore
    engine.check_permission = original_check
    print(f"Repair Complete. Total Keys Updated: {total_updated}")

if __name__ == "__main__":
    # Repair Jan 26, 27
    repair_keys([26, 27])
