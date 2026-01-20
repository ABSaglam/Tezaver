#!/usr/bin/env python3
"""
🧪 V4 MULTI-DAY TEST — COMMITTED_EARLY Impact Analysis
Comparing v4 (with COMMITTED_EARLY) against v3+ baseline
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from ralli_asm_15m_v4 import RalliASM15M_v4

def calc_max_drawdown(df, entry_idx, exit_idx, entry_price):
    if entry_idx >= exit_idx:
        return 0.0
    trade_candles = df.iloc[entry_idx:exit_idx+1]
    min_price = trade_candles['low'].min()
    return (min_price / entry_price - 1) * 100

def test_single_day(symbol, test_date, df):
    start = pd.Timestamp(test_date) - timedelta(days=1)
    end = pd.Timestamp(test_date) + timedelta(days=2)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    
    if len(test_df) < 100:
        return None, f"Insufficient data"
    
    asm = RalliASM15M_v4(test_df, verbose=False)
    signals = asm.run_simulation(start_idx=50)
    
    for trade in asm.trades:
        entry_idx = test_df[test_df['datetime'] == trade['entry_time']].index[0]
        exit_idx = test_df[test_df['datetime'] == trade['exit_time']].index[0]
        trade['max_dd'] = calc_max_drawdown(test_df, entry_idx, exit_idx, trade['entry_price'])
    
    return asm.trades, None

def main():
    symbol = 'ALGOUSDT'
    test_dates = ['2024-12-06', '2024-11-29', '2024-11-15', '2024-10-23', '2024-09-18']
    
    print("🧪 V4 MULTI-DAY TEST — COMMITTED_EARLY Impact")
    print(f"Symbol: {symbol}")
    print("="*80)
    
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    all_trades = []
    early_touches = 0
    full_convictions = 0
    
    for test_date in test_dates:
        print(f"\n📅 {test_date}")
        print("-"*60)
        
        trades, error = test_single_day(symbol, test_date, df)
        
        if error:
            print(f"  ⚠️ {error}")
            continue
        
        if not trades:
            print("  ⚪ No trades")
        else:
            for i, t in enumerate(trades, 1):
                status = "✅" if t['pnl_pct'] > 0 else "❌"
                print(f"  #{i} [{t['entry_type']}]:")
                print(f"    Entry: {t['entry_time']} @ {t['entry_price']:.4f}")
                print(f"    Exit:  {t['exit_time']} @ {t['exit_price']:.4f}")
                print(f"    PnL: {t['pnl_pct']:+.2f}% {status} | Max DD: {t['max_dd']:.2f}%")
                print(f"    Exit: {t['exit_reason']}")
                
                if 'EARLY' in t['entry_type']:
                    early_touches += 1
                elif 'FULL' in t['entry_type']:
                    full_convictions += 1
                    
                all_trades.append({'date': test_date, **t})
        
        print(f"  Total: {len(trades) if trades else 0}")
    
    print("\n" + "="*80)
    print("📊 V4 OVERALL SUMMARY")
    print("="*80)
    
    if all_trades:
        total = len(all_trades)
        winners = sum(1 for t in all_trades if t['pnl_pct'] > 0)
        total_pnl = sum(t['pnl_pct'] for t in all_trades)
        
        print(f"  Total Trades: {total}")
        print(f"  EARLY_TOUCH: {early_touches}")
        print(f"  FULL_CONVICTION: {full_convictions}")
        print(f"  Win Rate: {winners/total*100:.1f}%")
        print(f"  Total PnL: {total_pnl:+.2f}%")
        print(f"  Avg PnL: {total_pnl/total:+.2f}%")
        print(f"  Worst DD: {min(t['max_dd'] for t in all_trades):.2f}%")
        
        print("\n  💡 V3+ Comparison:")
        print("     V3+: 3 trades on 1 day, total PnL -0.70%")
        print(f"     V4:  {total} trades on {len([d for d in test_dates if any(t['date']==d for t in all_trades)])} days, total PnL {total_pnl:+.2f}%")
    else:
        print("  No trades generated.")

if __name__ == "__main__":
    main()
