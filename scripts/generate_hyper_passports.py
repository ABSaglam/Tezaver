"""
Hyper-Personalized Passport Generator (V2)
===========================================
Creates custom entry protocols for each coin based on its unique 
behavior profile identified in Phase 5.
"""

import os
import json
import pandas as pd
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

PROFILE_PATH = coin_cell_paths.get_library_root() / "coin_behavior_profiles.json"
OUTPUT_PATH = coin_cell_paths.get_library_root() / "coin_passports_hyper.json"

def create_hyper_passport():
    if not PROFILE_PATH.exists():
        print("❌ Error: Behavior profiles not found.")
        return

    with open(PROFILE_PATH, 'r') as f:
        profiles = json.load(f)

    passports = []

    for symbol, profile in profiles.items():
        # Custom Protocol Generation
        # We use Q25-Q75 range for RSI as it represents the 'comfort zone'
        # We use Q25 as absolute minimum for ATR and Volume
        
        # Safety Clamping: Don't let RSI max go above 85 or min below 30
        rsi_min = max(30, round(profile['rsi']['q25'], 1))
        rsi_max = min(85, round(profile['rsi']['q75'], 1))
        
        # If the range is too narrow (less than 10 units), expand it slightly around median
        if rsi_max - rsi_min < 10:
            median = profile['rsi']['median']
            rsi_min = max(30, round(median - 5, 1))
            rsi_max = min(85, round(median + 5, 1))

        # ATR Min: Use Q25 but cap it reasonably
        atr_min = round(profile['atr']['q25'], 2)
        
        # Vol Ratio Min: Use Q25 but cap it reasonably (at least 0.8)
        vol_min = max(0.8, round(profile['vol_ratio']['q25'], 2))

        # Tier breakdown from profile
        tier_dist = profile.get('tier_distribution', {})
        
        passport = {
            'symbol': symbol,
            'sample_size': profile['sample_size'],
            'tier_distribution': tier_dist,
            'protocol': {
                'rsi': {'min': rsi_min, 'max': rsi_max},
                'atr': {'min': atr_min},
                'vol_ratio': {'min': vol_min}
            }
        }
        
        passports.append(passport)

    with open(OUTPUT_PATH, 'w') as f:
        json.dump(passports, f, indent=2)

    print(f"✅ Successfully generated {len(passports)} hyper-personalized passports.")
    print(f"Saved to: {OUTPUT_PATH}")

    # Display some interesting examples
    examples = ['PEPEUSDT', 'RADUSDT', 'FTTUSDT', 'SOLUSDT', 'BTCUSDT']
    print("\n--- PASSPORT EXAMPLES ---")
    for ex in examples:
        p = next((x for x in passports if x['symbol'] == ex), None)
        if p:
            proto = p['protocol']
            print(f"{ex:12} | RSI: {proto['rsi']['min']}-{proto['rsi']['max']} | ATR Min: {proto['atr']['min']} | Vol Min: {proto['vol_ratio']['min']}")

if __name__ == "__main__":
    create_hyper_passport()
