import pandas as pd
import numpy as np
import os
import json

class IgnitorEngine:
    def __init__(self, soul_path="ignition_soul_manifest.json"):
        self.soul = {}
        if os.path.exists(soul_path):
            with open(soul_path, "r") as f:
                self.soul = json.load(f)
                
    def get_threshold(self, symbol):
        # Default to 5.0 (Oracle threshold) if not in soul
        return self.soul.get(symbol, 5.0)

    def analyze_sequence(self, df_15m, t0_idx):
        """
        Validates the 3-bar Ignition Sequence:
        T0: Ignition (Volume > Threshold)
        T1: Heat (Volume > 2.0x, Price holds)
        T2: Burn (RSI rising, Momentum confirms)
        """
        if t0_idx + 2 >= len(df_15m):
            return False, "Insufficient bars"
            
        # Indicators needed
        # Assuming df_15m already has 'rsi', 'rsi_ema', 'vol_ma', 'tr'
        
        t0 = df_15m.iloc[t0_idx]
        t1 = df_15m.iloc[t0_idx + 1]
        t2 = df_15m.iloc[t0_idx + 2]
        
        # 1. T0 Checks
        vol_ratio_t0 = t0['volume'] / (t0['vol_ma'] if t0['vol_ma'] > 0 else 0.001)
        if vol_ratio_t0 < self.get_threshold(t0.name if hasattr(t0, 'name') else "UNKNOWN"):
            return False, f"T0 Volume too low ({vol_ratio_t0:.1f})"
            
        # 2. T1 Checks
        vol_ratio_t1 = t1['volume'] / (t1['vol_ma'] if t1['vol_ma'] > 0 else 0.001)
        if vol_ratio_t1 < 2.0:
            return False, f"T1 Heat failed ({vol_ratio_t1:.1f})"
        
        if t1['close'] < t0['open']:
            return False, "T1 Price retrace too deep"
            
        # 3. T2 Checks
        if t2['rsi'] < t0['rsi']:
            return False, "T2 Momentum cooling (RSI drop)"
            
        if t2['rsi_ema'] <= t1['rsi_ema']:
            return False, "T2 Trend slope negative"
            
        return True, "IGNITION GRANTED"

if __name__ == "__main__":
    # Test stub
    engine = IgnitorEngine()
    print(f"Engine loaded with {len(engine.soul)} soul keys.")
