#!/usr/bin/env python3
"""
📍 OPTIMAL ENTRY/EXIT FINDER

Her rallinin GERÇEKten EN İYİ entry/exit noktalarını bulur.
Teorik kurallar değil - geriye dönük optimal timing.

Her rally için:
1. En düşük risk entry noktası (ilk güçlü hareket öncesi)
2. En iyi exit noktası (peak'e yakın ama güvenli)
"""

import json
import numpy as np

class OptimalPointFinder:
    """Finds actual optimal entry/exit for each rally"""
    
    def __init__(self, rally_data_path, cluster_path):
        with open(rally_data_path, 'r') as f:
            self.rally_data = json.load(f)
        
        with open(cluster_path, 'r') as f:
            cluster_info = json.load(f)
            self.assignments = {a['date']: a['cluster'] for a in cluster_info['rally_assignments']}
    
    def find_optimal_entry(self, candles):
        """
        Find optimal entry point:
        - Before significant move starts
        - Lowest reasonable entry price
        - Must have some confirming signal
        """
        if len(candles) < 10:
            return None
        
        # Find peak
        highs = [c['high'] for c in candles]
        peak_idx = highs.index(max(highs))
        peak_high = max(highs)
        
        # Look at first 20 candles or up to peak
        search_window = min(20, peak_idx)
        
        best_entry = None
        best_score = -999
        
        for idx in range(search_window):
            c = candles[idx]
            
            # Calculate if this would be a good entry
            # Score based on:
            # 1. Early (lower score for later entries)
            # 2. Low price (better entry)
            # 3. Has confirming signal (volume, EMA)
            
            # Potential gain from this entry
            potential_gain = (peak_high / c['close'] - 1) * 100
            
            # Earliness bonus (prefer earlier)
            earliness = 1 - (idx / search_window)
            
            # Signal quality
            signal_quality = 0
            if c.get('vol_ratio') and c['vol_ratio'] > 1.3:
                signal_quality += 0.3
            if c.get('ema9') and c.get('ema21'):
                if c['ema9'] > c['ema21']:
                    signal_quality += 0.3
            if c['close'] > c['open']:  # Green candle
                signal_quality += 0.2
            
            # Combined score
            score = potential_gain * 0.5 + earliness * 20 + signal_quality * 10
            
            if score > best_score:
                best_score = score
                best_entry = {
                    'idx': idx,
                    'timestamp': c['timestamp'],
                    'price': c['close'],
                    'potential_gain': potential_gain,
                    'signal_quality': signal_quality,
                    'score': score
                }
        
        return best_entry
    
    def find_optimal_exit(self, entry_idx, candles):
        """
        Find optimal exit:
        - Near peak but with safety margin
        - Before significant reversal
        """
        if entry_idx is None or entry_idx >= len(candles) - 1:
            return None
        
        # Entry is a dict, candles is the actual candle data
        entry_candle = candles[entry_idx]
        entry_price = entry_candle['close']
        
        # Find peak after entry
        post_entry = candles[entry_idx:]
        highs = [c['high'] for c in post_entry]
        peak_idx_relative = highs.index(max(highs))
        peak_idx_absolute = entry_idx + peak_idx_relative
        peak_high = max(highs)
        
        # Don't exit before at least 2 candles
        if peak_idx_absolute < entry_idx + 2:
            peak_idx_absolute = min(entry_idx + 2, len(candles) - 1)
        
        # Look for exit within 5 candles after peak
        exit_search_start = peak_idx_absolute
        exit_search_end = min(peak_idx_absolute + 5, len(candles))
        
        best_exit = None
        best_score = -999
        
        for idx in range(exit_search_start, exit_search_end):
            c = candles[idx]
            
            # Calculate exit quality
            pnl = (c['close'] / entry_price - 1) * 100
            
            # Distance from peak (prefer closer to peak)
            distance_from_peak = idx - peak_idx_absolute
            
            # Decline from peak
            decline_from_peak = (c['close'] / peak_high - 1) * 100
            
            # Score: Maximize PnL, minimize distance from peak, avoid big declines
            score = pnl * 2 - distance_from_peak * 5 - abs(decline_from_peak) * 3
            
            if score > best_score:
                best_score = score
                best_exit = {
                    'idx': idx,
                    'timestamp': c['timestamp'],
                    'price': c['close'],
                    'pnl': pnl,
                    'decline_from_peak': decline_from_peak,
                    'candles_after_peak': distance_from_peak,
                    'score': score
                }
        
        return best_exit
    
    def analyze_rally(self, rally):
        """Find optimal entry/exit for a rally"""
        date = rally['date']
        candles = rally['15m_data']
        cluster_id = self.assignments.get(date)
        
        entry = self.find_optimal_entry(candles)
        
        if entry is None:
            return None
        
        exit_data = self.find_optimal_exit(entry['idx'], candles)
        
        if exit_data is None:
            return None
        
        # Calculate max DD
        trade_candles = candles[entry['idx']:exit_data['idx']+1]
        max_dd = min((c['low'] / entry['price'] - 1) * 100 for c in trade_candles)
        
        return {
            'date': date,
            'tier': rally['tier'],
            'rally_pct': rally['rally_pct'],
            'cluster': cluster_id,
            'entry': entry,
            'exit': exit_data,
            'max_dd': round(max_dd, 2),
            'candles_held': exit_data['idx'] - entry['idx']
        }
    
    def analyze_all(self):
        """Analyze all 26 rallies"""
        print("📍 Finding OPTIMAL entry/exit for each rally...")
        print("="*80)
        
        results = []
        
        for rally in self.rally_data:
            result = self.analyze_rally(rally)
            
            if result:
                results.append(result)
                
                print(f"\n✅ {result['date']} (Cluster {result['cluster']})")
                print(f"   Entry: Candle {result['entry']['idx']} @ {result['entry']['price']:.4f}")
                print(f"   Exit: Candle {result['exit']['idx']} @ {result['exit']['price']:.4f}")
                print(f"   PnL: {result['exit']['pnl']:+.2f}% | Max DD: {result['max_dd']:.2f}%")
                print(f"   Signal Quality: {result['entry']['signal_quality']:.2f}")
        
        return results
    
    def generate_report(self, results):
        """Generate comprehensive report"""
        print("\n" + "="*80)
        print("📊 OPTIMAL ENTRY/EXIT ANALYSIS")
        print("="*80)
        
        total = len(results)
        total_pnl = sum(r['exit']['pnl'] for r in results)
        avg_pnl = total_pnl / total if total > 0 else 0
        
        print(f"\nTotal Rallies Analyzed: {total}/26")
        print(f"Total PnL (optimal): {total_pnl:+.2f}%")
        print(f"Avg PnL per Rally: {avg_pnl:+.2f}%")
        print(f"Worst Max DD: {min(r['max_dd'] for r in results):.2f}%")
        
        # Entry timing analysis
        print(f"\n📍 ENTRY TIMING PATTERNS:")
        early_entries = [r for r in results if r['entry']['idx'] <= 5]
        mid_entries = [r for r in results if 5 < r['entry']['idx'] <= 15]
        late_entries = [r for r in results if r['entry']['idx'] > 15]
        
        print(f"  Early (0-5 candles): {len(early_entries)} rallies")
        print(f"  Mid (6-15 candles): {len(mid_entries)} rallies")
        print(f"  Late (16+ candles): {len(late_entries)} rallies")
        
        # Per cluster analysis
        print(f"\n📊 PER CLUSTER:")
        for cluster_id in range(4):
            cluster_results = [r for r in results if r['cluster'] == cluster_id]
            if cluster_results:
                avg_entry_idx = np.mean([r['entry']['idx'] for r in cluster_results])
                avg_signal_q = np.mean([r['entry']['signal_quality'] for r in cluster_results])
                cluster_pnl = sum(r['exit']['pnl'] for r in cluster_results)
                
                print(f"\n  Cluster {cluster_id}:")
                print(f"    Rallies: {len(cluster_results)}")
                print(f"    Avg Entry Candle: {avg_entry_idx:.1f}")
                print(f"    Avg Signal Quality: {avg_signal_q:.2f}")
                print(f"    Total PnL: {cluster_pnl:+.2f}%")
        
        # Save
        output_path = "/Users/alisaglam/TezaverMac/data/optimal_entry_exit.json"
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📁 Results saved: {output_path}")
        
        return results

def main():
    rally_data_path = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"
    cluster_path = "/Users/alisaglam/TezaverMac/data/algo_rally_clusters.json"
    
    finder = OptimalPointFinder(rally_data_path, cluster_path)
    results = finder.analyze_all()
    finder.generate_report(results)
    
    print("\n💡 NEXT: Learn entry patterns from these optimal points")

if __name__ == "__main__":
    main()
