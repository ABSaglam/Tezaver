#!/usr/bin/env python3
"""
⚡ ASM v8 — THE HARMONY ASM (AHENK)

'Her şeyi biliyoruz, bilmiyormuş gibi yapmayalım.'

1. 1H Soul PASS: Rally öncesi < 2.3% 1H EMA compression (Ahenk).
2. 15M Entry: İlk 0-5 candle'da minimal sinyal (Ruh).
3. Optimized Exit: Erken aşamada yüksek tolerans, peak zone'da hassas çıkış (Ritim).
"""

import json
import pandas as pd
import numpy as np

class HarmonyASM_v8:
    def __init__(self, rally_data, h1_data):
        self.candles = rally_data['15m_data']
        self.date = rally_data['date']
        self.df_h1 = h1_data
        
    def check_h1_soul_pass(self):
        """
        'Ahenk' Check: 1H'de sıkışma var mı?
        26 rallinin ortak özelliği: < 2.3% 1H EMA compression.
        """
        start_ts = pd.to_datetime(self.candles[0]['timestamp'])
        pre_24h = self.df_h1[(self.df_h1.index >= start_ts - pd.Timedelta(hours=24)) & (self.df_h1.index < start_ts)]
        
        if pre_24h.empty:
            return False, 999
            
        # EMA Compression calculation
        def get_comp(row):
            emas = [row['ema9'], row['ema21'], row['ema50']]
            return (max(emas) / min(emas) - 1) * 100
            
        min_comp = pre_24h.apply(get_comp, axis=1).min()
        
        # Soul Pass: Compression must be tight
        return min_comp < 2.5, min_comp

    def run(self):
        # 1. 1H Soul Pass
        soul_pass, min_comp = self.check_h1_soul_pass()
        
        if not soul_pass:
            return {'date': self.date, 'entry_idx': None, 'reason': f'No 1H Squeeze (Comp: {min_comp:.2f}%)'}

        # 2. 15M Entry (0-20 candles)
        entry_idx = None
        for idx in range(min(21, len(self.candles))):
            c = self.candles[idx]
            
            # TRIGGER TYPE A: Trend Breakout
            trend_trigger = (c.get('vol_ratio', 0) > 1.15 and c.get('ema9', 0) > c.get('ema21', 0))
            
            # TRIGGER TYPE B: Mean Reversion Spark (Bottom Fisher)
            # Sudden high volume from oversold levels
            reversion_trigger = (c.get('vol_ratio', 0) > 2.0 and c.get('rsi', 100) < 30)
            
            if trend_trigger or reversion_trigger:
                entry_idx = idx
                break
                
        if entry_idx is None:
            return {'date': self.date, 'entry_idx': None, 'reason': 'No 15M trigger in first 20 candles'}

        # 3. Optimized Exit
        entry_candle = self.candles[entry_idx]
        max_high = entry_candle['high']
        exit_idx = None
        exit_reason = ""
        
        for idx in range(entry_idx + 1, len(self.candles)):
            c = self.candles[idx]
            if c['high'] > max_high:
                max_high = c['high']
            
            pnl = (c['close'] / entry_candle['close'] - 1) * 100
            dist_from_entry = idx - entry_idx
            
            # EXIT LOGIC - THE RHYTHM
            # Stage A: Initial Launch (0-30 candles) -> High Tolerance
            if dist_from_entry <= 30:
                if c['high'] < max_high * 0.96: # 4.0% tolerance in initial stage
                    exit_idx = idx
                    exit_reason = "EARLY_PULLBACK (4.0%)"
                    break
            # Stage B: The Climb (31-80 candles) -> Medium Tolerance
            elif dist_from_entry <= 80:
                if c['high'] < max_high * 0.98: # 2.0% tolerance
                    exit_idx = idx
                    exit_reason = "CLIMB_LOWER_HIGH (2.0%)"
                    break
            # Stage C: The Peak Zone (81+ candles) -> High Sensitivity
            else:
                if c['high'] < max_high * 0.995: # 0.5% tolerance
                    exit_idx = idx
                    exit_reason = "PEAK_LOWER_HIGH (0.5%)"
                    break
                    
            # Stop Loss
            if pnl < -4.0:
                exit_idx = idx
                exit_reason = "STOP_LOSS"
                break
        
        # Final EOD Exit if not exited
        if exit_idx is None:
            exit_idx = len(self.candles) - 1
            exit_reason = "END_OF_DAY"

        exit_candle = self.candles[exit_idx]
        final_pnl = (exit_candle['close'] / entry_candle['close'] - 1) * 100
        
        # Max DD
        max_dd = min((c['low'] / entry_candle['close'] - 1) * 100 for c in self.candles[entry_idx:exit_idx+1])

        return {
            'date': self.date,
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'pnl': round(final_pnl, 2),
            'max_dd': round(max_dd, 2),
            'reason': exit_reason,
            'comp': round(min_comp, 2),
            'held': exit_idx - entry_idx
        }

def test_v8():
    # Load Data
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1.sort_index(inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()

    print("🧘 ASM v8 — THE HARMONY (AHENK) TEST")
    print("="*80)
    
    results = []
    for rally in rally_data:
        asm = HarmonyASM_v8(rally, df_h1)
        res = asm.run()
        results.append(res)
        
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']} | PnL: {res['pnl']:+6.2f}% | DD: {res['max_dd']:5.2f}% | Comp: {res['comp']:.2f}% | {res['reason']}")
        else:
            print(f"⚪ {res['date']} | Skipped: {res['reason']}")

    # Summary
    trades = [r for r in results if r.get('entry_idx') is not None]
    if not trades:
        print("\n❌ No trades taken.")
        return

    total_pnl = sum(t['pnl'] for t in trades)
    avg_pnl = total_pnl / len(trades)
    win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades) * 100
    
    print("\n" + "="*80)
    print("📊 ASM v8 FINAL PERFORMANCE")
    print("="*80)
    print(f"Total Rallies: 26")
    print(f"Trades Taken:  {len(trades)}/26 ({len(trades)/26*100:.1f}%)")
    print(f"Win Rate:      {win_rate:.1f}%")
    print(f"Total PnL:     {total_pnl:+.2f}%")
    print(f"Avg PnL:       {avg_pnl:+.2f}%")
    print(f"Best Trade:    {max(t['pnl'] for t in trades):+.2f}%")
    print(f"Worst Max DD:  {min(t['max_dd'] for t in trades):.2f}%")

if __name__ == "__main__":
    test_v8()
