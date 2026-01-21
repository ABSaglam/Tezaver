#!/usr/bin/env python3
"""
⚡ ASM v14 — BALANCED SNIPER

'Zamanı koru, ama iştahı da kaçırma.'

- Start Search at C40.
- Trigger: Mikro-Ahenk (%0.8 squeeze) + Vol > 0.8.
- BALANCED VETO: Sinyalden sonraki 2 mumda (30 dk) fiyat en az %0.8 artmalı. (v13 %1.2/3m idi)
- Target: v13'ün hızını koruyup v12'nin kârına yaklaşmak.
"""

import json
import pandas as pd
import numpy as np

class BalancedSniper_v14:
    def __init__(self, rally_data, h1_data):
        self.candles = rally_data['15m_data']
        self.date = rally_data['date']
        self.df_h1 = h1_data
        
    def check_h1_soul_pass(self):
        start_ts = pd.to_datetime(self.candles[0]['timestamp'])
        pre_24h = self.df_h1[(self.df_h1.index >= start_ts - pd.Timedelta(hours=24)) & (self.df_h1.index < start_ts)]
        if pre_24h.empty: return False, 999
        def get_comp(row):
            emas = [row['ema9'], row['ema21'], row['ema50']]
            return (max(emas) / min(emas) - 1) * 100
        min_comp = pre_24h.apply(get_comp, axis=1).min()
        return min_comp < 2.5, min_comp

    def run(self):
        soul_pass, min_comp = self.check_h1_soul_pass()
        if not soul_pass:
            return {'date': self.date, 'entry_idx': None, 'reason': 'No 1H Squeeze'}

        entry_idx = None
        
        # SEARCH WINDOW (C40+)
        for idx in range(40, len(self.candles) - 3):
            c = self.candles[idx]
            emas = [c.get('ema9', 0), c.get('ema21', 0), c.get('ema50', 0)]
            if 0 in emas: continue
            local_comp = (max(emas) / min(emas) - 1) * 100
            
            if local_comp < 1.0 and c.get('vol_ratio', 0) > 0.8:
                # BALANCED VETO (2 candles, 0.8%)
                validation_candle = self.candles[idx + 2]
                move_pct = (validation_candle['close'] / c['close'] - 1) * 100
                
                if move_pct >= 0.8:
                    entry_idx = idx + 2
                    break
        
        if entry_idx is None:
            return {'date': self.date, 'entry_idx': None, 'reason': 'VETO: Balanced momentum not met'}

        entry_candle = self.candles[entry_idx]
        max_high = entry_candle['high']
        max_velocity = 0
        burst_active = False
        exit_idx = None
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            if c['high'] > max_high: max_high = c['high']
            pnl = (c['close'] / entry_candle['close'] - 1) * 100
            
            # Velocity Tracking for Exit
            if idx >= entry_idx + 5:
                prev_5 = self.candles[idx-5]
                velocity = (c['close'] / prev_5['close'] - 1) * 100
                if velocity > max_velocity: max_velocity = velocity
                if velocity >= 1.5: burst_active = True
                
                if burst_active:
                    if velocity < max_velocity * 0.6:
                        exit_idx = idx
                        break
                    if c['high'] < max_high * 0.992:
                        exit_idx = idx
                        break
            
            if pnl < -2.5 or idx > 94:
                exit_idx = idx
                break

        if exit_idx is None: exit_idx = len(self.candles) - 1
        exit_c = self.candles[exit_idx]
        final_pnl = (exit_c['close'] / entry_candle['close'] - 1) * 100
        
        return {
            'date': self.date,
            'entry_idx': entry_idx,
            'pnl': round(final_pnl, 2),
            'held': exit_idx - entry_idx
        }

def test_v14():
    import sys
    import os
    sys.path.append(os.getcwd())
    import scripts.test_turbo_on_59_journey as tester
    tester.TurboSniper_v12 = BalancedSniper_v14
    
    print("⚖️ ASM v14 — BALANCED SNIPER TEST")
    print("="*80)
    tester.run_turbo_on_59_journey_days()

if __name__ == "__main__":
    test_v14()
