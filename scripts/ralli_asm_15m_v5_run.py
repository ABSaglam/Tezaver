#!/usr/bin/env python3
"""
ASM v5 - Rally Soul Based State Machine
Uses empirical rules from 26 actual ALGO rallies
"""

import json
from datetime import datetime

# ---- VERİ YOLLARI ----
RALLY_DATA_FILE = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"

# ---- PARAMETRELER (Rally Soul'dan çıkarıldı) ----
EMA_FAST = 9
EMA_SLOW = 21
EMA_ANCHOR = 50
RSI_LOW, RSI_HIGH = 60, 70  # IQR from soul analysis
VOL_RATIO_THRESHOLD = 2.2   # Median from soul analysis
MAX_COMMITTED_MUM = 8

# ---- ASM DURUMLARI ----
STATE_IDLE = "IDLE"
STATE_SQUEEZED = "SQUEEZED"
STATE_AWAKENING = "AWAKENING"
STATE_COMMITTED = "COMMITTED"
STATE_EXTENSION = "EXTENSION"
STATE_EXHAUSTED = "EXHAUSTED"

# ---- YARDIMCI FONKSİYONLAR ----
def load_rally_data(path):
    with open(path, "r") as f:
        return json.load(f)

def check_committed(candle):
    """Check if candle meets COMMITTED criteria (Rally Soul Rules)"""
    # Handle None values
    if any(candle.get(k) is None for k in ['ema9', 'ema21', 'ema50', 'rsi', 'vol_ratio']):
        return False
    
    # RULE 1: EMA Alignment (100% required in real rallies)
    ema_aligned = candle['ema9'] > candle['ema21'] > candle['ema50']
    
    # RULE 2: RSI Range (60-70 IQR from soul)
    rsi_ok = RSI_LOW <= candle['rsi'] <= RSI_HIGH
    
    # RULE 3: Volume (>2.2 median from soul)
    vol_ok = candle['vol_ratio'] >= VOL_RATIO_THRESHOLD
    
    return ema_aligned and rsi_ok and vol_ok

def check_exhausted(candle, prev_candles, entry_idx, current_idx):
    """Check if rally is exhausted"""
    if not prev_candles or current_idx <= entry_idx:
        return False, ""
    
    # Get candles since entry
    candles_since_entry = prev_candles[entry_idx:current_idx+1]
    
    if len(candles_since_entry) < 2:
        return False, ""
    
    # CONDITION 1: LOWER HIGH
    # Current high is lower than previous swing high
    max_high_before = max(c['high'] for c in candles_since_entry[:-1])
    if candle['high'] < max_high_before * 0.998:  # 0.2% tolerance
        return True, "LOWER_HIGH"
    
    # CONDITION 2: EMA9 broken decisively
    if candle['close'] < candle['ema9'] * 0.995:  # 0.5% below EMA9
        return True, "EMA9_BROKEN"
    
    # CONDITION 3: Volume spike with red candle (blow-off)
    if candle['vol_ratio'] > 4.0 and candle['close'] < candle['open']:
        return True, "VOLUME_SPIKE"
    
    # CONDITION 4: Time decay (no new high after 10 candles)
    if len(candles_since_entry) >= 10:
        recent_high = max(c['high'] for c in candles_since_entry)
        entry_high = candles_since_entry[0]['high']
        gain = (recent_high / entry_high - 1) * 100
        if gain < 0.5:  # Less than 0.5% gain
            return True, "TIME_DECAY"
    
    return False, ""

# ---- ASM v5 RUN ----
def run_ralli_asm_15m(rally_data):
    """Run ASM v5 on a single rally day"""
    candles = rally_data['15m_data']
    
    state = STATE_IDLE
    committed_this_session = False
    entry_idx = None
    entry_price = None
    trades = []
    
    for idx, candle in enumerate(candles):
        # STATE TRANSITIONS
        if state == STATE_IDLE and not committed_this_session:
            if check_committed(candle):
                state = STATE_COMMITTED
                committed_this_session = True
                entry_idx = idx
                entry_price = candle['close']
                trades.append({
                    "timestamp": candle['timestamp'],
                    "state": STATE_COMMITTED,
                    "action": "BUY",
                    "entry_price": candle['close'],
                    "entry_idx": idx
                })
        
        elif state == STATE_COMMITTED:
            exhausted, reason = check_exhausted(candle, candles, entry_idx, idx)
            if exhausted:
                state = STATE_EXHAUSTED
                pnl = ((candle['close'] - entry_price) / entry_price) * 100
                
                # Calculate max drawdown
                candles_held = candles[entry_idx:idx+1]
                max_dd = min((c['low'] / entry_price - 1) * 100 for c in candles_held)
                
                trades.append({
                    "timestamp": candle['timestamp'],
                    "state": STATE_EXHAUSTED,
                    "action": "SELL",
                    "exit_price": candle['close'],
                    "exit_reason": reason,
                    "pnl_pct": round(pnl, 2),
                    "max_dd": round(max_dd, 2),
                    "candles_held": idx - entry_idx
                })
                state = STATE_IDLE
            elif idx - entry_idx > MAX_COMMITTED_MUM:
                state = STATE_EXTENSION
        
        elif state == STATE_EXTENSION:
            exhausted, reason = check_exhausted(candle, candles, entry_idx, idx)
            if exhausted:
                state = STATE_EXHAUSTED
                pnl = ((candle['close'] - entry_price) / entry_price) * 100
                
                candles_held = candles[entry_idx:idx+1]
                max_dd = min((c['low'] / entry_price - 1) * 100 for c in candles_held)
                
                trades.append({
                    "timestamp": candle['timestamp'],
                    "state": STATE_EXHAUSTED,
                    "action": "SELL",
                    "exit_price": candle['close'],
                    "exit_reason": reason,
                    "pnl_pct": round(pnl, 2),
                    "max_dd": round(max_dd, 2),
                    "candles_held": idx - entry_idx
                })
                state = STATE_IDLE
    
    return trades

# ---- ANA AKIŞ ----
if __name__ == "__main__":
    print("🚀 ASM v5 - RALLY SOUL BASED")
    print("="*80)
    print(f"Rules: EMA9>21>50, RSI {RSI_LOW}-{RSI_HIGH}, Vol>{VOL_RATIO_THRESHOLD}")
    print("="*80)
    
    rally_data = load_rally_data(RALLY_DATA_FILE)
    
    all_trades = []
    rally_summary = []
    
    for rally in rally_data:
        date = rally['date']
        tier = rally['tier']
        rally_pct = rally['rally_pct']
        
        print(f"\n📅 {date} ({tier}, {rally_pct:+.1f}%)")
        
        trades = run_ralli_asm_15m(rally)
        
        if trades:
            buy_trades = [t for t in trades if t['action'] == 'BUY']
            sell_trades = [t for t in trades if t['action'] == 'SELL']
            
            if buy_trades and sell_trades:
                buy = buy_trades[0]
                sell = sell_trades[0]
                
                all_trades.extend(trades)
                
                status = "✅" if sell['pnl_pct'] > 0 else "❌"
                print(f"   {status} BUY @ {buy['timestamp']} | Price: {buy['entry_price']:.4f}")
                print(f"   {status} SELL @ {sell['timestamp']} | Price: {sell['exit_price']:.4f}")
                print(f"   PnL: {sell['pnl_pct']:+.2f}% | Max DD: {sell['max_dd']:.2f}% | Reason: {sell['exit_reason']}")
                
                rally_summary.append({
                    'date': date,
                    'tier': tier,
                    'rally_pct': rally_pct,
                    'entry': buy['entry_price'],
                    'exit': sell['exit_price'],
                    'pnl': sell['pnl_pct'],
                    'max_dd': sell['max_dd'],
                    'exit_reason': sell['exit_reason']
                })
            else:
                print(f"   ⚠️ Incomplete trade (BUY without SELL)")
        else:
            print(f"   ⚪ No COMMITTED state reached")
    
    # FINAL REPORT
    print("\n" + "="*80)
    print("📊 ASM v5 FINAL REPORT")
    print("="*80)
    
    if rally_summary:
        total_trades = len(rally_summary)
        winners = sum(1 for t in rally_summary if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in rally_summary)
        avg_pnl = total_pnl / total_trades
        worst_dd = min(t['max_dd'] for t in rally_summary)
        
        print(f"\nTotal Rallies Tested: 26")
        print(f"Trades Executed: {total_trades}")
        print(f"Win Rate: {winners/total_trades*100:.1f}% ({winners}/{total_trades})")
        print(f"Total PnL: {total_pnl:+.2f}%")
        print(f"Avg PnL per Trade: {avg_pnl:+.2f}%")
        print(f"Worst Max DD: {worst_dd:.2f}%")
        
        # Exit reason distribution
        from collections import Counter
        exit_reasons = Counter(t['exit_reason'] for t in rally_summary)
        print(f"\nExit Reasons:")
        for reason, count in exit_reasons.most_common():
            print(f"  {reason}: {count}")
        
        # Save report
        report_path = "/Users/alisaglam/TezaverMac/data/asm_v5_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                'summary': {
                    'total_rallies': 26,
                    'trades_executed': total_trades,
                    'win_rate': winners/total_trades*100,
                    'total_pnl': total_pnl,
                    'avg_pnl': avg_pnl,
                    'worst_dd': worst_dd
                },
                'trades': rally_summary,
                'exit_reasons': dict(exit_reasons)
            }, f, indent=2)
        
        print(f"\n📁 Report saved: {report_path}")
    else:
        print("\n❌ No trades executed")
