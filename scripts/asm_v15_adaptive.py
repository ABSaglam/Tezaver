#!/usr/bin/env python3
"""
⚡ ASM v15 — THE ADAPTIVE SNIPER

'Hırçın koinleri (RIF vb.) ehlileştirmek için tasarlandı.'

- Start Search at C40.
- Trigger: Mikro-Ahenk (%0.8 squeeze) + Vol > 1.2 (Sıkılaştırıldı).
- VETO: 2 mumda %1.0 artış (Sıkılaştırıldı).
- FLASH STOP: Intra-candle %2.0 stop.
- BREAKEVEN: +%1.5 kâr görünce stop'u girişe çek.
"""

import json
import pandas as pd
import numpy as np

class AdaptiveSniper_v15:
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
        
        for idx in range(40, len(self.candles) - 3):
            c = self.candles[idx]
            emas = [c.get('ema9', 0), c.get('ema21', 0), c.get('ema50', 0)]
            if 0 in emas: continue
            local_comp = (max(emas) / min(emas) - 1) * 100
            
            # STRENGHTENED TRIGGER
            if local_comp < 1.0 and c.get('vol_ratio', 0) > 1.2:
                # STRENGHTENED VETO (1.0% in 2 candles)
                validation_candle = self.candles[idx + 2]
                move_pct = (validation_candle['close'] / c['close'] - 1) * 100
                
                if move_pct >= 1.0:
                    entry_idx = idx + 2
                    break
        
        if entry_idx is None:
            return {'date': self.date, 'entry_idx': None, 'reason': 'VETO: Momentum validation failed'}

        entry_candle = self.candles[entry_idx]
        max_high = entry_candle['high']
        max_pnl = 0
        exit_idx = None
        stop_level = -2.5 # Base Stop
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            pnl = (c['close'] / entry_candle['close'] - 1) * 100
            high_pnl = (c['high'] / entry_candle['close'] - 1) * 100
            low_pnl = (c['low'] / entry_candle['close'] - 1) * 100
            
            if high_pnl > max_pnl: max_pnl = high_pnl
            if c['high'] > max_high: max_high = c['high']
            
            # BREAKEVEN LOGIC
            if max_pnl >= 1.5:
                stop_level = 0.0 # Move stop to entry
            
            # EMERGENCY INTRA-CANDLE STOP
            if low_pnl < stop_level:
                exit_idx = idx
                break
                
            # VELOCITY EXIT
            if idx >= entry_idx + 5:
                prev_5 = self.candles[idx-5]
                velocity = (c['close'] / prev_5['close'] - 1) * 100
                if velocity < -1.0: # Negative velocity crash
                    exit_idx = idx
                    break
            
            if idx > 94:
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

if __name__ == "__main__":
    # Test on RIF
    import sys
    import os
    sys.path.append(os.getcwd())
    import scripts.test_rif_ayas_v14 as tester
    tester.BalancedSniper_v14 = AdaptiveSniper_v15
    print("🌪️ ASM v15 — ADAPTIVE SNIPER TEST (RIF)")
    print("="*80)
    tester.scan_rif_ayas_days()
