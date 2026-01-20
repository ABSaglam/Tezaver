#!/usr/bin/env python3
"""
ASM v6 - Phase 4: Core ASM with Adaptive + MTF + Patterns

Integrates all v6 features:
- Adaptive thresholds (IQR-based)
- Multi-timeframe confirmation
- Enhanced exit with candle patterns
"""

import json
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from asm_v6_mtf_checker import MTFChecker
from asm_v6_candle_patterns import CandlePatternDetector

class RalliASM_v6:
    """ASM v6 with adaptive thresholds and MTF confirmation"""
    
    def __init__(self, rally_data, config, use_mtf=True, use_patterns=True):
        self.candles = rally_data['15m_data']
        self.config = config['adaptive_config']
        self.mode = config.get('recommended_mode', 'relaxed')
        
        self.use_mtf = use_mtf
        self.use_patterns = use_patterns
        
        # MTF checker
        self.mtf_checker = MTFChecker(config['coin']) if use_mtf else None
        
        # State
        self.state = 'IDLE'
        self.entry_idx = None
        self.entry_price = None
        self.trades = []
    
    def _check_committed(self, candle):
        """Check COMMITTED using adaptive thresholds"""
        # Handle None values
        if any(candle.get(k) is None for k in ['ema9', 'ema21', 'ema50', 'rsi', 'vol_ratio']):
            return False
        
        # RULE 1: EMA Alignment (always required)
        if not self.config['ema_alignment_required']:
            return False
        
        ema_aligned = candle['ema9'] > candle['ema21'] > candle['ema50']
        if not ema_aligned:
            return False
        
        # RULE 2: RSI (adaptive)
        rsi_config = self.config['rsi']
        if self.mode == 'strict':
            rsi_ok = rsi_config['threshold_strict'][0] <= candle['rsi'] <= rsi_config['threshold_strict'][1]
        else:  # relaxed
            rsi_ok = rsi_config['threshold_relaxed'][0] <= candle['rsi'] <= rsi_config['threshold_relaxed'][1]
        
        if not rsi_ok:
            return False
        
        # RULE 3: Volume (adaptive)
        vol_config = self.config['vol_ratio']
        if self.mode == 'strict':
            vol_ok = candle['vol_ratio'] >= vol_config['threshold_strict']
        else:  # relaxed
            vol_ok = candle['vol_ratio'] >= vol_config['threshold_relaxed']
        
        return vol_ok
    
    def _check_exhausted(self, idx):
        """Check if rally is exhausted with enhanced exit logic"""
        if self.entry_idx is None or idx <= self.entry_idx:
            return False, ""
        
        candle = self.candles[idx]
        candles_since_entry = self.candles[self.entry_idx:idx+1]
        
        if len(candles_since_entry) < 2:
            return False, ""
        
        # CONDITION 1: LOWER HIGH
        max_high_before = max(c['high'] for c in candles_since_entry[:-1])
        if candle['high'] < max_high_before * 0.998:
            return True, "LOWER_HIGH"
        
        # CONDITION 2: EMA9 BROKEN
        if candle['close'] < candle['ema9'] * 0.995:
            return True, "EMA9_BROKEN"
        
        # CONDITION 3: CANDLE PATTERNS (if enabled)
        if self.use_patterns and idx > 0:
            prev_candle = self.candles[idx-1]
            patterns = CandlePatternDetector.detect_all_patterns(prev_candle, candle)
            
            # Bearish engulfing or shooting star are strong signals
            if 'BEARISH_ENGULFING' in patterns:
                return True, "BEARISH_ENGULFING"
            if 'SHOOTING_STAR' in patterns:
                return True, "SHOOTING_STAR"
        
        # CONDITION 4: VOLUME SPIKE (blow-off)
        if candle['vol_ratio'] > 4.0 and candle['close'] < candle['open']:
            return True, "VOLUME_SPIKE"
        
        # CONDITION 5: TIME DECAY
        if len(candles_since_entry) >= 15:
            recent_high = max(c['high'] for c in candles_since_entry)
            entry_high = candles_since_entry[0]['high']
            gain = (recent_high / entry_high - 1) * 100
            if gain < 1.0:
                return True, "TIME_DECAY"
        
        return False, ""
    
    def run(self):
        """Run ASM v6 on rally data"""
        committed_this_session = False
        
        for idx, candle in enumerate(self.candles):
            # State: IDLE → COMMITTED
            if self.state == 'IDLE' and not committed_this_session:
                if self._check_committed(candle):
                    # Optional: MTF confirmation
                    mtf_confirmed = True
                    mtf_confidence = 'HIGH'
                    
                    if self.use_mtf and self.mtf_checker:
                        mtf_result = self.mtf_checker.get_mtf_confirmation(candle['timestamp'])
                        mtf_confirmed = mtf_result['confirmed']
                        mtf_confidence = mtf_result['confidence']
                    
                    # For relaxed mode, we allow LOW confidence with MTF
                    # For strict mode, we require HIGH confidence
                    if self.mode == 'relaxed' or mtf_confirmed:
                        self.state = 'COMMITTED'
                        committed_this_session = True
                        self.entry_idx = idx
                        self.entry_price = candle['close']
                        
                        self.trades.append({
                            'action': 'BUY',
                            'timestamp': candle['timestamp'],
                            'price': candle['close'],
                            'entry_idx': idx,
                            'mtf_confirmed': mtf_confirmed,
                            'mtf_confidence': mtf_confidence
                        })
            
            # State: COMMITTED/EXTENSION → EXHAUSTED
            elif self.state in ['COMMITTED', 'EXTENSION']:
                exhausted, reason = self._check_exhausted(idx)
                
                if exhausted:
                    self.state = 'EXHAUSTED'
                    
                    # Calculate PnL and max DD
                    pnl = (candle['close'] / self.entry_price - 1) * 100
                    candles_held = self.candles[self.entry_idx:idx+1]
                    max_dd = min((c['low'] / self.entry_price - 1) * 100 for c in candles_held)
                    
                    self.trades.append({
                        'action': 'SELL',
                        'timestamp': candle['timestamp'],
                        'price': candle['close'],
                        'exit_idx': idx,
                        'exit_reason': reason,
                        'pnl_pct': round(pnl, 2),
                        'max_dd': round(max_dd, 2),
                        'candles_held': idx - self.entry_idx
                    })
                    
                    self.state = 'IDLE'
                
                elif idx - self.entry_idx > 8:
                    self.state = 'EXTENSION'
        
        return self.trades

def run_v6_on_rallies(rally_data_path, config_path, use_mtf=True, use_patterns=True):
    """Run ASM v6 on all rally days"""
    
    # Load data
    with open(rally_data_path, 'r') as f:
        rally_data = json.load(f)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print(f"🚀 ASM v6 - {config['recommended_mode'].upper()} Mode")
    print(f"   MTF: {'✅' if use_mtf else '❌'}")
    print(f"   Patterns: {'✅' if use_patterns else '❌'}")
    print("="*80)
    
    all_trades = []
    rally_summary = []
    
    for rally in rally_data:
        date = rally['date']
        tier = rally['tier']
        rally_pct = rally['rally_pct']
        
        print(f"\n📅 {date} ({tier}, {rally_pct:+.1f}%)")
        
        asm = RalliASM_v6(rally, config, use_mtf=use_mtf, use_patterns=use_patterns)
        trades = asm.run()
        
        if trades:
            buy_trades = [t for t in trades if t['action'] == 'BUY']
            sell_trades = [t for t in trades if t['action'] == 'SELL']
            
            if buy_trades and sell_trades:
                buy = buy_trades[0]
                sell = sell_trades[0]
                
                status = "✅" if sell['pnl_pct'] > 0 else "❌"
                mtf_flag = "🎯" if buy.get('mtf_confirmed') else "⚠️"
                
                print(f"   {status} {mtf_flag} BUY @ {buy['timestamp']} | Price: {buy['price']:.4f}")
                print(f"   {status} SELL @ {sell['timestamp']} | Price: {sell['price']:.4f}")
                print(f"   PnL: {sell['pnl_pct']:+.2f}% | Max DD: {sell['max_dd']:.2f}% | Reason: {sell['exit_reason']}")
                
                rally_summary.append({
                    'date': date,
                    'tier': tier,
                    'rally_pct': rally_pct,
                    'entry': buy['price'],
                    'exit': sell['price'],
                    'pnl': sell['pnl_pct'],
                    'max_dd': sell['max_dd'],
                    'exit_reason': sell['exit_reason'],
                    'mtf_confirmed': bool(buy.get('mtf_confirmed', False)),
                    'mtf_confidence': buy.get('mtf_confidence', 'UNKNOWN')
                })
                
                all_trades.extend(trades)
        else:
            print(f"   ⚪ No COMMITTED state reached")
    
    # FINAL REPORT
    print("\n" + "="*80)
    print("📊 ASM v6 FINAL REPORT")
    print("="*80)
    
    if rally_summary:
        total_trades = len(rally_summary)
        winners = sum(1 for t in rally_summary if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in rally_summary)
        avg_pnl = total_pnl / total_trades
        worst_dd = min(t['max_dd'] for t in rally_summary)
        
        mtf_confirmed_count = sum(1 for t in rally_summary if t['mtf_confirmed'])
        
        print(f"\nTotal Rallies Tested: 26")
        print(f"Trades Executed: {total_trades}")
        print(f"MTF Confirmed: {mtf_confirmed_count}/{total_trades}")
        print(f"Win Rate: {winners/total_trades*100:.1f}% ({winners}/{total_trades})")
        print(f"Total PnL: {total_pnl:+.2f}%")
        print(f"Avg PnL per Trade: {avg_pnl:+.2f}%")
        print(f"Worst Max DD: {worst_dd:.2f}%")
        
        # Exit reason distribution
        exit_reasons = Counter(t['exit_reason'] for t in rally_summary)
        print(f"\nExit Reasons:")
        for reason, count in exit_reasons.most_common():
            print(f"  {reason}: {count}")
        
        # Save report
        report = {
            'config': {
                'mode': config['recommended_mode'],
                'mtf_enabled': bool(use_mtf),
                'patterns_enabled': bool(use_patterns)
            },
            'summary': {
                'total_rallies': 26,
                'trades_executed': total_trades,
                'mtf_confirmed': mtf_confirmed_count,
                'win_rate': winners/total_trades*100,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'worst_dd': worst_dd
            },
            'trades': rally_summary,
            'exit_reasons': dict(exit_reasons)
        }
        
        report_path = "/Users/alisaglam/TezaverMac/data/asm_v6_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📁 Report saved: {report_path}")
    else:
        print("\n❌ No trades executed")
    
    return rally_summary

if __name__ == "__main__":
    rally_data_path = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"
    config_path = "/Users/alisaglam/TezaverMac/data/algo_adaptive_config_v6.json"
    
    run_v6_on_rallies(rally_data_path, config_path, use_mtf=True, use_patterns=True)
    
    print("\n✅ Phase 4 Complete!")
