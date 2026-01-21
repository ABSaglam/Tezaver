#!/usr/bin/env python3
"""
⚡ ASM v9 — INTENSITY (YOĞUNLUK ODAKLI)

'80-90 mum beklenmez, ralli şiştiği an çıkılır.'

- 1H Squeeze: Ahenk kontrolü.
- 15M Entry: Ruh kontrolü (Trend + Reversion).
- Intensity Exit: 5 mumluk hızı takip eder, hız kesildiği an kârı alır.
"""

import json
import pandas as pd
import numpy as np

class IntensityASM_v9:
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
            return {'date': self.date, 'entry_idx': None, 'reason': f'No 1H Squeeze'}

        # Entry (Trend or Reversion)
        entry_idx = None
        for idx in range(min(21, len(self.candles))):
            c = self.candles[idx]
            trend = (c.get('vol_ratio', 0) > 1.15 and c.get('ema9', 0) > c.get('ema21', 0))
            reversion = (c.get('vol_ratio', 0) > 2.0 and c.get('rsi', 100) < 30)
            if trend or reversion:
                entry_idx = idx
                break
        
        if entry_idx is None:
            return {'date': self.date, 'entry_idx': None, 'reason': 'No 15M trigger'}

        entry_candle = self.candles[entry_idx]
        max_high = entry_candle['high']
        max_velocity = 0
        burst_active = False
        exit_idx = None
        exit_reason = ""
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            if c['high'] > max_high: max_high = c['high']
            
            # Velocity: 5-candle rolling PnL
            if idx >= entry_idx + 5:
                prev_5 = self.candles[idx-5]
                velocity = (c['close'] / prev_5['close'] - 1) * 100
                if velocity > max_velocity: max_velocity = velocity
                
                # Burst Detection (> 2.5% in 5 candles)
                if velocity >= 2.5:
                    burst_active = True
                
                # EXIT LOGIC - INTENSITY BASED
                if burst_active:
                    # 1. Deceleration: Velocity dropped 40% from its peak
                    if velocity < max_velocity * 0.6:
                        exit_idx = idx
                        exit_reason = f"BURST_EXHAUSTED (Vel: {velocity:.1f}%)"
                        break
                    # 2. Micro-Pullback: 0.8% from local peak high
                    if c['high'] < max_high * 0.992:
                        exit_idx = idx
                        exit_reason = "BURST_PULLBACK (0.8%)"
                        break
            
            # Hard Stop Loss
            if (c['close'] / entry_candle['close'] - 1) * 100 < -4.0:
                exit_idx = idx
                exit_reason = "STOP_LOSS"
                break
                
            # Time Cap: Don't wait past C75 regardless
            if idx > 75:
                exit_idx = idx
                exit_reason = "TIME_CAP (C75)"
                break

        if exit_idx is None:
            exit_idx = len(self.candles) - 1
            exit_reason = "END_OF_DAY"

        exit_c = self.candles[exit_idx]
        pnl = (exit_c['close'] / entry_candle['close'] - 1) * 100
        return {
            'date': self.date,
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'pnl': round(pnl, 2),
            'reason': exit_reason,
            'held': exit_idx - entry_idx
        }

def test_v9():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    print("🚀 ASM v9 — INTENSITY (YOĞUNLUK) TEST")
    print("="*80)
    results = []
    for rally in rally_data:
        asm = IntensityASM_v9(rally, df_h1)
        res = asm.run()
        results.append(res)
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']} | PnL: {res['pnl']:+6.2f}% | Held: {res['held']:2} | {res['reason']}")
    
    trades = [r for r in results if r.get('entry_idx') is not None]
    print("\n" + "="*80)
    print(f"TOTAL PNL: {sum(t['pnl'] for t in trades):+.2f}% | AVG HELD: {sum(t['held'] for t in trades)/len(trades):.1f} candles")

if __name__ == "__main__":
    test_v9()
