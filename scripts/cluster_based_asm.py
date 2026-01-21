#!/usr/bin/env python3
"""
🎯 CLUSTER-BASED PATTERN MATCHING ASM

Her ralliye cluster assignment'ına göre özel entry/exit stratejisi uygular.
Test eder: 26 rallinin hepsini yakalayabilir miyiz?
"""

import json
import numpy as np

class ClusterBasedASM:
    """Pattern matching ASM - cluster'a göre strateji"""
    
    def __init__(self, rally_data_path, cluster_path):
        # Load rally data
        with open(rally_data_path, 'r') as f:
            self.rally_data = json.load(f)
        
        # Load cluster assignments
        with open(cluster_path, 'r') as f:
            cluster_info = json.load(f)
            self.assignments = {a['date']: a['cluster'] for a in cluster_info['rally_assignments']}
    
    def get_cluster_strategy(self, cluster_id):
        """Get entry/exit strategy for each cluster"""
        strategies = {
            0: {  # Sudden Death
                'name': 'Sudden Death',
                'entry': 'PULLBACK_WAIT',
                'entry_patience': 10,  # Wait up to 10 candles for pullback
                'exit': 'FIRST_WEAKNESS',  # Exit aggressively
                'exit_sensitivity': 'HIGH',  # Low tolerance
                'lower_high_threshold': 0.999  # 0.1% threshold (very sensitive)
            },
            1: {  # Classic Grind (majority)
                'name': 'Classic Grind',
                'entry': 'F3_F4_PATTERN',
                'entry_patience': 15,  # Can wait longer
                'exit': 'LOWER_HIGH_EMA9',
                'exit_sensitivity': 'MEDIUM',
                'lower_high_threshold': 0.998  # 0.2% threshold
            },
            2: {  # Fast & Furious
                'name': 'Fast & Furious',
                'entry': 'IMMEDIATE',  # Don't wait!
                'entry_patience': 0,  # No waiting
                'exit': 'FIRST_WEAKNESS',
                'exit_sensitivity': 'HIGH',
                'lower_high_threshold': 0.999
            },
            3: {  # Steady Builder
                'name': 'Steady Builder',
                'entry': 'STANDARD_COMMITTED',
                'entry_patience': 8,
                'exit': 'LOWER_HIGH',
                'exit_sensitivity': 'MEDIUM',
                'lower_high_threshold': 0.998
            }
        }
        return strategies.get(cluster_id, strategies[1])  # Default to Classic Grind
    
    def check_entry_immediate(self, idx, candles):
        """Immediate entry - first strong signal"""
        if idx < 3:
            return False
        
        c = candles[idx]
        
        # Basic entry: EMA9>21, green candle, decent volume
        if c.get('ema9') and c.get('ema21') and c.get('vol_ratio'):
            if c['ema9'] > c['ema21'] and c['close'] > c['open'] and c['vol_ratio'] > 1.5:
                return True
        return False
    
    def check_entry_pullback_wait(self, idx, candles):
        """Wait for pullback then enter on reclaim"""
        if idx < 5:
            return False
        
        c = candles[idx]
        prev_5 = candles[max(0, idx-5):idx]
        
        # Check if there was a pullback recently
        had_pullback = any(pc['close'] < pc.get('ema9', 0) for pc in prev_5 if pc.get('ema9'))
        
        # Now reclaiming EMA9
        if had_pullback and c.get('ema9'):
            if c['close'] > c['ema9'] and c['ema9'] > c.get('ema21', 0):
                return True
        
        return False
    
    def check_entry_f3_f4(self, idx, candles):
        """Classic F3→F4 pattern"""
        if idx < 10:
            return False
        
        c = candles[idx]
        last_10 = candles[idx-10:idx]
        
        # Find if there was a local high followed by pullback
        if len(last_10) < 5:
            return False
        
        highs = [h['high'] for h in last_10]
        max_high = max(highs)
        max_high_idx = highs.index(max_high)
        
        # After max_high, did we pull back?
        if max_high_idx < len(last_10) - 2:
            post_high = last_10[max_high_idx+1:]
            min_low_post = min(h['low'] for h in post_high)
            pullback_pct = (min_low_post / max_high - 1) * 100
            
            # If pullback >= 1% and now reclaiming
            if pullback_pct < -1.0:
                if c.get('ema9') and c['close'] > c['ema9']:
                    return True
        
        return False
    
    def check_entry_standard(self, idx, candles):
        """Standard COMMITTED conditions"""
        if idx < 5:
            return False
        
        c = candles[idx]
        
        if not all(c.get(k) for k in ['ema9', 'ema21', 'ema50', 'rsi', 'vol_ratio']):
            return False
        
        # EMA alignment
        ema_ok = c['ema9'] > c['ema21'] > c['ema50']
        
        # RSI reasonable
        rsi_ok = 55 <= c['rsi'] <= 75
        
        # Volume decent
        vol_ok = c['vol_ratio'] > 1.8
        
        return ema_ok and rsi_ok and vol_ok
    
    def find_entry(self, candles, strategy, max_wait=20):
        """Find entry point based on strategy"""
        entry_type = strategy['entry']
        
        for idx in range(min(max_wait, len(candles))):
            if entry_type == 'IMMEDIATE':
                if self.check_entry_immediate(idx, candles):
                    return idx, 'IMMEDIATE'
            elif entry_type == 'PULLBACK_WAIT':
                if self.check_entry_pullback_wait(idx, candles):
                    return idx, 'PULLBACK_RECLAIM'
            elif entry_type == 'F3_F4_PATTERN':
                if self.check_entry_f3_f4(idx, candles):
                    return idx, 'F3_F4'
            elif entry_type == 'STANDARD_COMMITTED':
                if self.check_entry_standard(idx, candles):
                    return idx, 'STANDARD'
        
        return None, None
    
    def find_exit(self, entry_idx, candles, strategy):
        """Find exit point based on strategy"""
        if entry_idx is None or entry_idx >= len(candles) - 1:
            return None, None
        
        entry_price = candles[entry_idx]['close']
        max_high = entry_price
        threshold = strategy['lower_high_threshold']
        
        for idx in range(entry_idx + 1, len(candles)):
            c = candles[idx]
            
            # Track max high
            if c['high'] > max_high:
                max_high = c['high']
            
            # LOWER HIGH check
            if idx > entry_idx + 2:  # At least 2 candles after entry
                if c['high'] < max_high * threshold:
                    pnl = (c['close'] / entry_price - 1) * 100
                    return idx, f"LOWER_HIGH (PnL: {pnl:+.2f}%)"
            
            # EMA9 broken (if strategy uses it)
            if 'EMA9' in strategy['exit']:
                if c.get('ema9') and c['close'] < c['ema9'] * 0.995:
                    pnl = (c['close'] / entry_price - 1) * 100
                    return idx, f"EMA9_BROKEN (PnL: {pnl:+.2f}%)"
            
            # Time decay (max 20 candles)
            if idx - entry_idx > 20:
                pnl = (c['close'] / entry_price - 1) * 100
                return idx, f"TIME_LIMIT (PnL: {pnl:+.2f}%)"
        
        # End of day without exit
        pnl = (candles[-1]['close'] / entry_price - 1) * 100
        return len(candles) - 1, f"EOD (PnL: {pnl:+.2f}%)"
    
    def test_rally(self, rally):
        """Test cluster-based strategy on a rally"""
        date = rally['date']
        cluster_id = self.assignments.get(date)
        
        if cluster_id is None:
            return None
        
        strategy = self.get_cluster_strategy(cluster_id)
        candles = rally['15m_data']
        
        # Find entry
        entry_idx, entry_type = self.find_entry(candles, strategy)
        
        if entry_idx is None:
            return {
                'date': date,
                'cluster': cluster_id,
                'cluster_name': strategy['name'],
                'entry': None,
                'reason': 'No entry signal'
            }
        
        entry_candle = candles[entry_idx]
        
        # Find exit
        exit_idx, exit_reason = self.find_exit(entry_idx, candles, strategy)
        
        if exit_idx is None:
            return {
                'date': date,
                'cluster': cluster_id,
                'cluster_name': strategy['name'],
                'entry': entry_candle['timestamp'],
                'exit': None,
                'reason': 'No exit found'
            }
        
        exit_candle = candles[exit_idx]
        pnl = (exit_candle['close'] / entry_candle['close'] - 1) * 100
        
        # Calculate max DD
        trade_candles = candles[entry_idx:exit_idx+1]
        max_dd = min((c['low'] / entry_candle['close'] - 1) * 100 for c in trade_candles)
        
        return {
            'date': date,
            'tier': rally['tier'],
            'rally_pct': rally['rally_pct'],
            'cluster': cluster_id,
            'cluster_name': strategy['name'],
            'entry_idx': entry_idx,
            'entry_time': entry_candle['timestamp'],
            'entry_price': entry_candle['close'],
            'entry_type': entry_type,
            'exit_idx': exit_idx,
            'exit_time': exit_candle['timestamp'],
            'exit_price': exit_candle['close'],
            'exit_reason': exit_reason,
            'pnl': round(pnl, 2),
            'max_dd': round(max_dd, 2),
            'candles_held': exit_idx - entry_idx
        }
    
    def test_all_rallies(self):
        """Test on all 26 rallies"""
        print("🎯 Testing Cluster-Based Pattern Matching ASM on 26 rallies")
        print("="*80)
        
        results = []
        
        for rally in self.rally_data:
            result = self.test_rally(rally)
            if result:
                results.append(result)
                
                if result.get('entry'):
                    status = "✅" if result['pnl'] > 0 else "❌"
                    print(f"\n{status} {result['date']} ({result['cluster_name']})")
                    print(f"   Entry: {result['entry_time']} @ {result['entry_price']:.4f} ({result['entry_type']})")
                    print(f"   Exit: {result['exit_time']} @ {result['exit_price']:.4f}")
                    print(f"   PnL: {result['pnl']:+.2f}% | Max DD: {result['max_dd']:.2f}%")
                    print(f"   Reason: {result['exit_reason']}")
                else:
                    print(f"\n⚪ {result['date']} ({result['cluster_name']})")
                    print(f"   {result.get('reason', 'Unknown reason')}")
        
        return results
    
    def generate_report(self, results):
        """Generate final report"""
        trades = [r for r in results if r.get('entry') is not None]
        
        print("\n" + "="*80)
        print("📊 CLUSTER-BASED ASM FINAL REPORT")
        print("="*80)
        
        if not trades:
            print("\n❌ No trades executed")
            return
        
        total_rallies = len(results)
        total_trades = len(trades)
        winners = sum(1 for t in trades if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in trades)
        
        print(f"\nTotal Rallies: {total_rallies}")
        print(f"Trades Executed: {total_trades}/{total_rallies} ({total_trades/total_rallies*100:.1f}%)")
        print(f"Win Rate: {winners/total_trades*100:.1f}% ({winners}/{total_trades})")
        print(f"Total PnL: {total_pnl:+.2f}%")
        print(f"Avg PnL per Trade: {total_pnl/total_trades:+.2f}%")
        print(f"Worst Max DD: {min(t['max_dd'] for t in trades):.2f}%")
        
        # Per cluster
        print(f"\n📊 PER CLUSTER PERFORMANCE:")
        for cluster_id in range(4):
            cluster_trades = [t for t in trades if t['cluster'] == cluster_id]
            if cluster_trades:
                cluster_wins = sum(1 for t in cluster_trades if t['pnl'] > 0)
                cluster_pnl = sum(t['pnl'] for t in cluster_trades)
                print(f"\n  Cluster {cluster_id} ({cluster_trades[0]['cluster_name']}):")
                print(f"    Trades: {len(cluster_trades)}")
                print(f"    Win Rate: {cluster_wins/len(cluster_trades)*100:.1f}%")
                print(f"    Total PnL: {cluster_pnl:+.2f}%")
        
        # Save
        output_path = "/Users/alisaglam/TezaverMac/data/cluster_asm_results.json"
        with open(output_path, 'w') as f:
            json.dump({
                'summary': {
                    'total_rallies': total_rallies,
                    'trades_executed': total_trades,
                    'coverage': total_trades/total_rallies*100,
                    'win_rate': winners/total_trades*100,
                    'total_pnl': total_pnl,
                    'avg_pnl': total_pnl/total_trades
                },
                'trades': trades
            }, f, indent=2)
        
        print(f"\n📁 Results saved: {output_path}")

def main():
    rally_data_path = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"
    cluster_path = "/Users/alisaglam/TezaverMac/data/algo_rally_clusters.json"
    
    asm = ClusterBasedASM(rally_data_path, cluster_path)
    results = asm.test_all_rallies()
    asm.generate_report(results)

if __name__ == "__main__":
    main()
