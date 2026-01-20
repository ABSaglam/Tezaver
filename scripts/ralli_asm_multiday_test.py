#!/usr/bin/env python3
"""
🧪 MULTI-DAY BEHAVIORAL CONSISTENCY TEST
Testing RALLI_ASM_15M v3+ on 5 known rally days (UNCHANGED)
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from ralli_asm_15m_v3plus import RalliASM15M_v3plus

def calc_max_drawdown(df, entry_idx, exit_idx, entry_price):
    """Calculate max drawdown during trade"""
    if entry_idx >= exit_idx:
        return 0.0
    trade_candles = df.iloc[entry_idx:exit_idx+1]
    min_price = trade_candles['low'].min()
    max_dd = (min_price / entry_price - 1) * 100
    return max_dd

def test_single_day(symbol, test_date, df):
    """Run ASM on a single day and return results"""
    start = pd.Timestamp(test_date) - timedelta(days=1)
    end = pd.Timestamp(test_date) + timedelta(days=2)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    
    if len(test_df) < 100:
        return None, f"Insufficient data for {test_date}"
    
    asm = RalliASM15M_v3plus(test_df, verbose=False)
    signals = asm.run_simulation(start_idx=50)
    
    # Calc max drawdown for each trade
    for trade in asm.trades:
        entry_idx = test_df[test_df['datetime'] == trade['entry_time']].index[0]
        exit_idx = test_df[test_df['datetime'] == trade['exit_time']].index[0]
        trade['max_dd'] = calc_max_drawdown(test_df, entry_idx, exit_idx, trade['entry_price'])
    
    return asm.trades, None

def main():
    symbol = 'ALGOUSDT'
    test_dates = [
        '2024-12-06',
        '2024-11-29',
        '2024-11-15',
        '2024-10-23',
        '2024-09-18'
    ]
    
    print("🧪 MULTI-DAY BEHAVIORAL CONSISTENCY TEST")
    print(f"System: RALLI_ASM_15M v3+ (UNCHANGED)")
    print(f"Symbol: {symbol}")
    print("="*80)
    
    # Load all 15M data
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    all_trades = []
    
    for test_date in test_dates:
        print(f"\n📅 RALLY DAY: {test_date}")
        print("-"*60)
        
        trades, error = test_single_day(symbol, test_date, df)
        
        if error:
            print(f"  ⚠️ {error}")
            continue
        
        if not trades:
            print("  ⚪ No trades (COMMITTED never reached)")
        else:
            for i, trade in enumerate(trades, 1):
                status = "✅" if trade['pnl_pct'] > 0 else "❌"
                print(f"  Trade #{i}:")
                print(f"    Entry: {trade['entry_time']} @ {trade['entry_price']:.4f}")
                print(f"    Exit:  {trade['exit_time']} @ {trade['exit_price']:.4f}")
                print(f"    PnL:   {trade['pnl_pct']:+.2f}%  {status}")
                print(f"    Max DD: {trade['max_dd']:.2f}%")
                print(f"    Candles: {trade['candles_held']}")
                print(f"    Exit Reason: {trade['exit_reason']}")
                all_trades.append({
                    'date': test_date,
                    **trade
                })
        
        print(f"  Total Trades: {len(trades) if trades else 0}")
    
    # Summary
    print("\n" + "="*80)
    print("📊 OVERALL SUMMARY")
    print("="*80)
    
    if all_trades:
        total_trades = len(all_trades)
        winners = sum(1 for t in all_trades if t['pnl_pct'] > 0)
        total_pnl = sum(t['pnl_pct'] for t in all_trades)
        avg_pnl = total_pnl / total_trades
        worst_dd = min(t['max_dd'] for t in all_trades)
        avg_candles = sum(t['candles_held'] for t in all_trades) / total_trades
        
        # Exit reason distribution
        exit_reasons = {}
        for t in all_trades:
            reason_type = t['exit_reason'].split(':')[0]
            exit_reasons[reason_type] = exit_reasons.get(reason_type, 0) + 1
        
        print(f"  Total Trades: {total_trades}")
        print(f"  Win Rate: {winners/total_trades*100:.1f}% ({winners}/{total_trades})")
        print(f"  Total PnL: {total_pnl:+.2f}%")
        print(f"  Avg PnL per Trade: {avg_pnl:+.2f}%")
        print(f"  Worst Max DD: {worst_dd:.2f}%")
        print(f"  Avg Candles Held: {avg_candles:.1f}")
        print(f"\n  Exit Reason Distribution:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}")
    else:
        print("  No trades generated across all test dates.")

if __name__ == "__main__":
    main()
