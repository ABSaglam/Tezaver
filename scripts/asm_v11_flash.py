#!/usr/bin/env python3
"""
⚡ ASM v11 — THE FLASH (HYPER-EFFICIENCY)

'Zaman en büyük maliyettir. 20 mumda işi bitir.'

- Sniper Entry: Mikro-Ahenk girişi.
- 20-Candle Hard Cap: Ne olursa olsun 20. mumda çıkış.
- Flash Profit: 10 mumda %3 kar varsa anında çıkış.
"""

import json
import pandas as pd
import numpy as np

class FlashASM_v11:
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

        # Sniper Entry
        entry_idx = None
        for idx in range(20, min(81, len(self.candles))):
            c = self.candles[idx]
            emas = [c.get('ema9', 0), c.get('ema21', 0), c.get('ema50', 0)]
            if 0 in emas: continue
            local_comp = (max(emas) / min(emas) - 1) * 100
            if local_comp < 0.8 and c.get('vol_ratio', 0) > 1.0:
                entry_idx = idx
                break
        
        if entry_idx is None:
            return {'date': self.date, 'entry_idx': None, 'reason': 'No 15M Sniper Trigger'}

        entry_candle = self.candles[entry_idx]
        exit_idx = None
        exit_reason = ""
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            pnl = (c['close'] / entry_candle['close'] - 1) * 100
            held = idx - entry_idx
            
            # FLASH EXIT RULES
            # 1. Hard Time Cap: 20 candles (5 hours)
            if held >= 20:
                exit_idx = idx
                exit_reason = "FLASH_TIME_CAP (20c)"
                break
                
            # 2. Hyper-Burst: 3% profit in < 10 candles
            if held < 10 and pnl >= 3.0:
                exit_idx = idx
                exit_reason = "FLASH_BURST_TAKE"
                break

            # 3. Stop Loss (Aggressive 2.5%)
            if pnl < -2.5:
                exit_idx = idx
                exit_reason = "FLASH_STOP_LOSS"
                break

        if exit_idx is None: exit_idx = len(self.candles) - 1
        exit_candle = self.candles[exit_idx]
        final_pnl = (exit_candle['close'] / entry_candle['close'] - 1) * 100
        
        return {
            'date': self.date,
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'pnl': round(final_pnl, 2),
            'held': exit_idx - entry_idx,
            'reason': exit_reason or "END_OF_DAY"
        }

def test_v11():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    print("⚡ ASM v11 — THE FLASH TEST")
    print("="*80)
    results = []
    for rally in rally_data:
        asm = FlashASM_v11(rally, df_h1)
        res = asm.run()
        results.append(res)
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']} | In: C{res['entry_idx']:2} | PnL: {res['pnl']:+6.2f}% | Held: {res['held']:2} | {res['reason']}")
    
    trades = [r for r in results if r.get('entry_idx') is not None]
    print("\n" + "="*80)
    total_pnl = sum(t['pnl'] for t in trades)
    avg_held = sum(t['held'] for t in trades)/len(trades)
    print(f"TOTAL PNL: {total_pnl:+.2f}% | AVG HELD: {avg_held:.1f} candles | EFFICIENCY (PnL/Held): {total_pnl/avg_held:.3f}")

if __name__ == "__main__":
    test_v11()
