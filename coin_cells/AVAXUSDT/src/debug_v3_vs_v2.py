import pandas as pd
import json
import sys
from pathlib import Path

# Paths
BASE_V2 = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn")
BASE_V3 = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v3/runs/run_001")

sys.path.append("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/src")
import avax_kader_simulator_elite as sim_v2
import avax_kader_simulator_v3 as sim_v3
import utils_io
import avax_learn_core
import core_indicators_v3

def debug_compare():
    print("::: V3 vs V2 LOGIC DEBUG :::")
    
    # Load Rules
    rules_v2 = sim_v2.load_elite_rules()
    rules_v3 = sim_v3.load_v3_rules()
    
    # Load Data
    data_bundle = utils_io.get_data_bundle("AVAXUSDT")
    df = avax_learn_core.calculate_technical_features(data_bundle['1d'], None, None, None)
    df = core_indicators_v3.calculate_extended_indicators(df)
    df = avax_learn_core.generate_labels(df)
    
    # Filter for known days
    target_dates = ["2025-12-02", "2025-11-30"] # Success, Fail
    
    for d in target_dates:
        print(f"\n--- ANALYZING {d} ---")
        row = df[df['datetime'].dt.strftime('%Y-%m-%d') == d].iloc[0]
        
        # Run V2
        dec_v2, tier_v2, verd_v2, reas_v2 = sim_v2.evaluate_elite_day(row, *rules_v2)
        print(f"V2 Decision: {dec_v2} ({reas_v2})")
        
        # Run V3
        dec_v3, tier_v3, verd_v3, reas_v3 = sim_v3.evaluate_day_v3(row, *rules_v3)
        print(f"V3 Decision: {dec_v3} ({reas_v3})")
        
        # Check Corridor Bounds Comparison
        # Check 'Energy_Gap' bounds in both
        val = row['Energy_Gap']
        b_v2 = rules_v2[1]['Energy_Gap']
        b_v3 = rules_v3[1]['Energy_Gap']
        print(f"Energy_Gap Val: {val:.4f}")
        print(f"V2 Bounds: {b_v2['min']:.4f} - {b_v2['max']:.4f}")
        print(f"V3 Bounds: {b_v3['min']:.4f} - {b_v3['max']:.4f}")

if __name__ == "__main__":
    debug_compare()
