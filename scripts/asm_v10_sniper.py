#!/usr/bin/env python3
"""
⚡ ASM v10 — THE SNIPER (TURBO ENTRY)

'Sabahın köründe değil, akşamın turbo vaktinde gir.'

- 1H Soul Pass: Ana sıkışma kontrolü.
- Late Search Window: C30'dan sonra asıl turboyu arar.
- 15M Mikro-Ahenk Entry: 15M EMAlar %0.8'den daha fazla sıkıştığında ve hacim geldiğinde girer.
- Velocity Exit: v9'un hızlı ve yoğunluk odaklı çıkışını kullanır.
"""

import json
import pandas as pd
import numpy as np

class SniperASM_v10:
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
        # Snipe Window: Search from C20 to C80 for the late burst
        for idx in range(20, min(81, len(self.candles))):
            c = self.candles[idx]
            
            # 15M Mikro-Ahenk (Compression)
            emas = [c.get('ema9', 0), c.get('ema21', 0), c.get('ema50', 0)]
            if 0 in emas: continue
            local_comp = (max(emas) / min(emas) - 1) * 100
            
            # Sniper Trigger: Squeeze < 0.8% AND Volume Ignition
            if local_comp < 0.8 and c.get('vol_ratio', 0) > 1.0:
                entry_idx = idx
                break
        
        if entry_idx is None:
            # Fallback to Early Entry if no late burst found but 1H pass is strong
            return {'date': self.date, 'entry_idx': None, 'reason': 'No 15M Sniper Trigger'}

        entry_candle = self.candles[entry_idx]
        max_high = entry_candle['high']
        max_velocity = 0
        burst_active = False
        exit_idx = None
        exit_reason = ""
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            if c['high'] > max_high: max_high = c['high']
            
            # Velocity Tracking
            if idx >= entry_idx + 5:
                prev_5 = self.candles[idx-5]
                velocity = (c['close'] / prev_5['close'] - 1) * 100
                if velocity > max_velocity: max_velocity = velocity
                if velocity >= 2.0: burst_active = True
                
                if burst_active:
                    if velocity < max_velocity * 0.6:
                        exit_idx = idx
                        exit_reason = "SNIPER_BURST_EXIT"
                        break
                    if c['high'] < max_high * 0.99:
                        exit_idx = idx
                        exit_reason = "SNIPER_PULLBACK_EXIT"
                        break
            
            if (c['close'] / entry_candle['close'] - 1) * 100 < -3.0:
                exit_idx = idx
                exit_reason = "STOP_LOSS"
                break
            
            if idx > 94:
                exit_idx = idx
                exit_reason = "END_OF_DAY"
                break

        if exit_idx is None: exit_idx = len(self.candles) - 1
        exit_candle = self.candles[exit_idx]
        pnl = (exit_candle['close'] / entry_candle['close'] - 1) * 100
        
        return {
            'date': self.date,
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'pnl': round(pnl, 2),
            'held': exit_idx - entry_idx,
            'reason': exit_reason or "END_OF_DAY"
        }

def test_v10():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    print("🎯 ASM v10 — THE SNIPER TEST")
    print("="*80)
    results = []
    for rally in rally_data:
        asm = SniperASM_v10(rally, df_h1)
        res = asm.run()
        results.append(res)
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']} | In: C{res['entry_idx']:2} | PnL: {res['pnl']:+6.2f}% | Held: {res['held']:2} | {res['reason']}")
    
    trades = [r for r in results if r.get('entry_idx') is not None]
    print("\n" + "="*80)
    print(f"TOTAL PNL: {sum(t['pnl'] for t in trades):+.2f}% | AVG HELD: {sum(t['held'] for t in trades)/len(trades):.1f} candles | COVERAGE: {len(trades)}/26")

if __name__ == "__main__":
    test_v10()
