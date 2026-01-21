#!/usr/bin/env python3
"""
⚡ ASM v12 — TURBO SNIPER (EXTREME EFFICIENCY)

'15 saatlik grind kısmını tamamen uykuda geçir, akşamki turboya gir.'

- Start Search at C40: Rallinin ilk 10 saatini tamamen yok say.
- Sniper Entry: C40-C80 arası Mikro-Ahenk (%0.8 squeeze) ara.
- Velocity Exit: Hız düştüğü an çık.
"""

import json
import pandas as pd
import numpy as np

class TurboSniper_v12:
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

        # TURBO ENTRY: Search only from C40 onwards
        entry_idx = None
        for idx in range(40, min(81, len(self.candles))):
            c = self.candles[idx]
            emas = [c.get('ema9', 0), c.get('ema21', 0), c.get('ema50', 0)]
            if 0 in emas: continue
            local_comp = (max(emas) / min(emas) - 1) * 100
            
            # Use slightly more relaxed trigger since we are in the turbo zone
            if local_comp < 1.0 and c.get('vol_ratio', 0) > 0.8:
                entry_idx = idx
                break
        
        if entry_idx is None:
            return {'date': self.date, 'entry_idx': None, 'reason': 'No Late Turbo Trigger'}

        entry_candle = self.candles[entry_idx]
        max_high = entry_candle['high']
        max_velocity = 0
        burst_active = False
        exit_idx = None
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            if c['high'] > max_high: max_high = c['high']
            
            pnl = (c['close'] / entry_candle['close'] - 1) * 100
            held = idx - entry_idx
            
            # Velocity Tracking
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

def test_v12():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    print("🚀 ASM v12 — TURBO SNIPER TEST")
    print("="*80)
    results = []
    for rally in rally_data:
        asm = TurboSniper_v12(rally, df_h1)
        res = asm.run()
        results.append(res)
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']} | In: C{res['entry_idx']:2} | PnL: {res['pnl']:+6.2f}% | Held: {res['held']:2}")
    
    trades = [r for r in results if r.get('entry_idx') is not None]
    total_pnl = sum(t['pnl'] for t in trades)
    avg_held = sum(t['held'] for t in trades)/len(trades)
    print("\n" + "="*80)
    print(f"TOTAL PNL: {total_pnl:+.2f}% | AVG HELD: {avg_held:.1f} candles | EFFICIENCY: {total_pnl/avg_held:.3f}")

if __name__ == "__main__":
    test_v12()
