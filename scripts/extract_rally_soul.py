#!/usr/bin/env python3
"""
🔬 RALLY SOUL EXTRACTOR
Analyzes 26 ALGO rally timelines to extract behavioral patterns
Creates ASM rules based on actual rally behavior
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import Counter

class RallySoulAnalyzer:
    """Extracts the 'soul' of ALGO rallies from timeline data"""
    
    def __init__(self, timeline_path, raw_data_path):
        # Load timeline (state transitions)
        with open(timeline_path, 'r') as f:
            self.timeline_data = json.load(f)
        
        # Load raw 15M data
        with open(raw_data_path, 'r') as f:
            self.raw_data = json.load(f)
        
        self.rally_patterns = []
    
    def analyze_single_rally(self, rally_timeline, rally_raw):
        """Analyze a single rally's behavior"""
        date = rally_timeline['date']
        states = rally_timeline['states']
        raw_candles = rally_raw['15m_data']
        
        # Build state timeline
        state_sequence = []
        prev_state = None
        for s in states:
            if s['state'] != prev_state:
                state_sequence.append({
                    'state': s['state'],
                    'timestamp': s['timestamp']
                })
                prev_state = s['state']
        
        # Find COMMITTED moments
        committed_moments = [s for s in states if s['state'] == 'COMMITTED']
        
        if not committed_moments:
            return None
        
        # Get first COMMITTED
        first_committed_ts = committed_moments[0]['timestamp']
        
        # Find corresponding raw candle
        committed_candle = next((c for c in raw_candles if c['timestamp'] == first_committed_ts), None)
        
        if not committed_candle:
            return None
        
        # Analyze conditions at COMMITTED
        pattern = {
            'date': date,
            'tier': rally_timeline['tier'],
            'rally_pct': rally_timeline['rally_pct'],
            'committed_time': first_committed_ts,
            'state_sequence': [s['state'] for s in state_sequence],
            'committed_conditions': {
                'ema9': committed_candle.get('ema9'),
                'ema21': committed_candle.get('ema21'),
                'ema50': committed_candle.get('ema50'),
                'ema_aligned': (committed_candle.get('ema9', 0) > committed_candle.get('ema21', 0) > committed_candle.get('ema50', 0)),
                'rsi': committed_candle.get('rsi'),
                'vol_ratio': committed_candle.get('vol_ratio'),
                'atr_ratio': committed_candle.get('atr', 0) / committed_candle.get('atr_ma', 1) if committed_candle.get('atr_ma') else None
            }
        }
        
        # Find pre-COMMITTED states
        committed_idx = next(i for i, s in enumerate(states) if s['state'] == 'COMMITTED')
        pre_states = states[max(0, committed_idx-10):committed_idx]
        pattern['pre_committed_states'] = [s['state'] for s in pre_states]
        
        return pattern
    
    def extract_rally_soul(self):
        """Extract common patterns across all rallies"""
        print("🔬 Analyzing 26 rally timelines...")
        print("="*80)
        
        for i, (timeline, raw) in enumerate(zip(self.timeline_data, self.raw_data)):
            print(f"\n📅 Rally #{i+1}: {timeline['date']} ({timeline['tier']}, {timeline['rally_pct']:+.1f}%)")
            
            pattern = self.analyze_single_rally(timeline, raw)
            
            if pattern:
                self.rally_patterns.append(pattern)
                rsi_val = pattern['committed_conditions']['rsi']
                vol_val = pattern['committed_conditions']['vol_ratio']
                print(f"   ✅ COMMITTED @ {pattern['committed_time']}")
                print(f"   State sequence: {' → '.join(pattern['state_sequence'][:5])}")
                rsi_str = f"{rsi_val:.0f}" if rsi_val is not None else "N/A"
                vol_str = f"{vol_val:.2f}" if vol_val is not None else "N/A"
                print(f"   Conditions: EMA={pattern['committed_conditions']['ema_aligned']}, "
                      f"RSI={rsi_str}, Vol={vol_str}")
            else:
                print(f"   ⚠️ No COMMITTED state found")
        
        print("\n" + "="*80)
        print("📊 RALLY SOUL EXTRACTION")
        print("="*80)
        
        # Statistical analysis
        total_rallies = len(self.rally_patterns)
        print(f"\nRallies with COMMITTED: {total_rallies}/26")
        
        # EMA alignment at COMMITTED
        ema_aligned_count = sum(1 for p in self.rally_patterns if p['committed_conditions']['ema_aligned'])
        print(f"\nEMA Alignment (9>21>50) at COMMITTED: {ema_aligned_count}/{total_rallies} ({ema_aligned_count/total_rallies*100:.1f}%)")
        
        # RSI distribution at COMMITTED
        rsi_values = [p['committed_conditions']['rsi'] for p in self.rally_patterns if p['committed_conditions']['rsi'] is not None]
        if rsi_values:
            print(f"\nRSI at COMMITTED:")
            print(f"  Min: {min(rsi_values):.1f}")
            print(f"  Max: {max(rsi_values):.1f}")
            print(f"  Mean: {np.mean(rsi_values):.1f}")
            print(f"  Median: {np.median(rsi_values):.1f}")
        
        # Volume ratio at COMMITTED
        vol_values = [p['committed_conditions']['vol_ratio'] for p in self.rally_patterns if p['committed_conditions']['vol_ratio'] is not None]
        if vol_values:
            print(f"\nVolume Ratio at COMMITTED:")
            print(f"  Min: {min(vol_values):.2f}")
            print(f"  Max: {max(vol_values):.2f}")
            print(f"  Mean: {np.mean(vol_values):.2f}")
            print(f"  Median: {np.median(vol_values):.2f}")
        
        # ATR ratio at COMMITTED
        atr_values = [p['committed_conditions']['atr_ratio'] for p in self.rally_patterns if p['committed_conditions']['atr_ratio'] is not None]
        if atr_values:
            print(f"\nATR/ATR_MA at COMMITTED:")
            print(f"  Min: {min(atr_values):.2f}")
            print(f"  Max: {max(atr_values):.2f}")
            print(f"  Mean: {np.mean(atr_values):.2f}")
            print(f"  Median: {np.median(atr_values):.2f}")
        
        # Most common state sequences
        print(f"\n🔄 COMMON STATE SEQUENCES (leading to COMMITTED):")
        all_sequences = []
        for p in self.rally_patterns:
            if len(p['state_sequence']) >= 2:
                # Get sequence up to COMMITTED
                seq_str = ' → '.join(p['state_sequence'][:4])
                all_sequences.append(seq_str)
        
        sequence_counts = Counter(all_sequences)
        for seq, count in sequence_counts.most_common(5):
            print(f"  {seq}: {count} rallies")
        
        # Derive ASM rules
        print("\n" + "="*80)
        print("🎯 RALLY SOUL RULES (for ASM v5)")
        print("="*80)
        
        # Rule 1: EMA Alignment
        if ema_aligned_count / total_rallies >= 0.7:
            print("\n✅ RULE 1: EMA Alignment REQUIRED")
            print("   EMA9 > EMA21 > EMA50 must be TRUE at COMMITTED")
        else:
            print("\n⚠️ RULE 1: EMA Alignment OPTIONAL")
            print(f"   Only {ema_aligned_count/total_rallies*100:.0f}% of rallies have full alignment")
        
        # Rule 2: RSI Range
        if rsi_values:
            rsi_25 = np.percentile(rsi_values, 25)
            rsi_75 = np.percentile(rsi_values, 75)
            print(f"\n✅ RULE 2: RSI Range")
            print(f"   RSI should be between {rsi_25:.0f} and {rsi_75:.0f} (IQR)")
            print(f"   Median: {np.median(rsi_values):.0f}")
        
        # Rule 3: Volume
        if vol_values:
            vol_median = np.median(vol_values)
            print(f"\n✅ RULE 3: Volume Ratio")
            print(f"   Volume ratio should be > {vol_median:.2f} (median)")
        
        # Rule 4: State Progression
        print(f"\n✅ RULE 4: State Progression")
        print(f"   Most common: AWAKENING → IDLE → COMMITTED")
        print(f"   Or: AWAKENING → COMMITTED (direct)")
        
        return {
            'total_rallies': total_rallies,
            'ema_aligned_pct': ema_aligned_count / total_rallies * 100,
            'rsi_range': (min(rsi_values), max(rsi_values)) if rsi_values else (None, None),
            'rsi_median': np.median(rsi_values) if rsi_values else None,
            'vol_median': np.median(vol_values) if vol_values else None,
            'patterns': self.rally_patterns
        }

def main():
    timeline_path = "/Users/alisaglam/TezaverMac/data/algo_rally_timeline_15m.json"
    raw_data_path = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"
    
    analyzer = RallySoulAnalyzer(timeline_path, raw_data_path)
    soul = analyzer.extract_rally_soul()
    
    # Save rally soul
    output_path = "/Users/alisaglam/TezaverMac/data/algo_rally_soul.json"
    with open(output_path, 'w') as f:
        json.dump({
            'total_rallies': soul['total_rallies'],
            'ema_aligned_pct': soul['ema_aligned_pct'],
            'rsi_range': soul['rsi_range'],
            'rsi_median': soul['rsi_median'],
            'vol_median': soul['vol_median'],
            'patterns': soul['patterns']
        }, f, indent=2)
    
    print(f"\n📁 Rally soul saved to: {output_path}")

if __name__ == "__main__":
    main()
