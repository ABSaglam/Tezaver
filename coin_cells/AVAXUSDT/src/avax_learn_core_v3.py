import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

import utils_io
import avax_learn_core # Re-use feature calc V17 basics
import core_indicators_v3 # NEW V3 Logic

SYMBOL = "AVAXUSDT"
TRAIN_START = pd.Timestamp("2023-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2025-12-31", tz="UTC")
OUT_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v3/runs/run_001")
RULES_DIR = OUT_DIR / "rules"
RULES_DIR.mkdir(parents=True, exist_ok=True)

def run_learning_v3():
    print("::: AVAX LEARNING CORE V3 (DNA RECONSTRUCTION) :::")
    
    # 1. Load Data
    data_bundle = utils_io.get_data_bundle(SYMBOL)
    df_daily = data_bundle['1d']
    df_4h = data_bundle['4h']
    df_1h = data_bundle['1h']
    
    # 2. V17 Feature Gen
    print("::: V17 Feature Gen :::")
    df_feat = avax_learn_core.calculate_technical_features(df_daily, None, None, None)
    
    # 3. V3 Extended Indicators
    print("::: V3 Extended Indicators (Ribbon/RSI-EMA) :::")
    df_feat = core_indicators_v3.calculate_extended_indicators(df_feat)
    
    # 4. Labeling & Filtering
    df_labeled = avax_learn_core.generate_labels(df_feat)
    # Anti-Hindsight: Labels use t+1, Features use t. Safe.
    
    mask_train = (df_labeled['datetime'] >= TRAIN_START) & (df_labeled['datetime'] <= TRAIN_END)
    df_train = df_labeled[mask_train].copy()
    
    print(f"Training Set: {len(df_train)} days. Hits: {len(df_train[df_train['Hit_10']=='YES'])}")
    
    # 5. LEARN STEP 1: FAIL ZONE (Hard Veto + Suppression)
    # Analyze NO days vs YES days
    fail_rules = {}
    
    # Standard V17 metrics veto
    cols = ['Wick_Ratio', 'Dist_EMA', 'ATR_Norm', 'Energy_Gap', 'Anti_Penalty', 'Drift_Factor']
    df_yes = df_train[df_train['Hit_10'] == 'YES']
    df_no = df_train[df_train['Hit_10'] == 'NO']
    
    for col in cols:
        min_yes = df_yes[col].quantile(0.02)
        max_yes = df_yes[col].quantile(0.98)
        
        # Check density of NOs
        # Only add rule if it catches signficant NOs
        caught_low = len(df_no[df_no[col] < min_yes])
        caught_high = len(df_no[df_no[col] > max_yes])
        
        rule = {}
        if caught_low > 5: rule['min_hard'] = float(min_yes)
        if caught_high > 5: rule['max_hard'] = float(max_yes)
        
        if rule:
            fail_rules[col] = rule
            
    # NEW: Suppression Veto Analysis
    # Does 'Ribbon Inside + RSI < RSI_EMA' correlate strongly with failure?
    suppression_days = df_train[df_train['STATE_RIBBON_SUPPRESSION_UP'] == True]
    supp_fail_rate = len(suppression_days[suppression_days['Hit_10']=='NO']) / len(suppression_days) if len(suppression_days) > 0 else 0
    print(f"Suppression Day Fail Rate: {supp_fail_rate*100:.1f}%")
    
    fail_rules['suppression_veto'] = {
        "active": (supp_fail_rate > 0.90), # Only vetos if >90% chance of fail
        "desc": "RIBBON_INSIDE + RSI < RSI_EMA implies trap"
    }

    # 6. LEARN STEP 2: SUCCESS CORRIDOR
    # INHERIT PROVEN ELITE V2 BOUNDS
    # We load the existing V2 rules to guarantee baseline performance match.
    v2_rules_path = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn/rules/avax_success_corridor_v2.json")
    
    if v2_rules_path.exists():
        with open(v2_rules_path) as f:
            success_corridor = json.load(f)
        print("Inherited Elite V2 Corridor Bounds.")
    else:
        # Fallback if V2 missing (should not happen in this env)
        success_corridor = {}
        for col in ['ATR_Norm', 'Energy_Gap', 'Wick_Ratio', 'Dist_EMA']:
            p10 = df_yes[col].quantile(0.15)
            p90 = df_yes[col].quantile(0.85)
            success_corridor[col] = {"min": float(p10), "max": float(p90)}

    # ADX: Ensure V3 Strict Floor overrides/confirms
    success_corridor['ADX'] = {"min": 35.0, "max": 100.0}
    
    # 7. LEARN STEP 3: INTRADAY CANCEL (4H/1H)
    # Generate statistics for ribbon conditions on FAIL days
    # We define a "Ribbon Trap" score implies cancellation.
    # For now, we supply the logic definition to be used by simulator.
    # We learn threshold if we had robust intraday data mapped to daily rows, 
    # but here we define the standard logic requested.
    cancel_rules = {
        "4h_ribbon_trap": {"check": True, "condition": "RIBBON_INSIDE and RSI < RSI_EMA"},
        "1h_ribbon_trap": {"check": True, "condition": "RIBBON_INSIDE and RSI < RSI_EMA"},
        "wick_ratio_4h": {"threshold": 0.28} # From previous ELITE analysis
    }

    # 8. LEARN STEP 4: TRIGGER MAP V3
    # Statistical breakdown of ignition types?
    # We supply the prioritized list.
    trigger_map = {
        "priority_types": ["RIBBON_BREAK+RSI_LOCK", "VOL_SPIKE+HOLD", "PIVOT_ONLY"],
        "min_vol_ratio_15m": 1.5,
        "required_rsi_lock_daily": True
    }
    
    # Save Rules
    utils_io.save_json_rule(fail_rules, RULES_DIR / "avax_fail_rules_v3.json")
    utils_io.save_json_rule(success_corridor, RULES_DIR / "avax_success_corridor_v3.json")
    utils_io.save_json_rule(cancel_rules, RULES_DIR / "avax_intraday_cancel_rules_v3.json")
    utils_io.save_json_rule(trigger_map, RULES_DIR / "avax_trigger_map_v3.json")
    
    print(f"Rules saved to {RULES_DIR}")

if __name__ == "__main__":
    run_learning_v3()
