#!/usr/bin/env python3
"""
🔬 PHASE-0: ALGO RALLY ANATOMY ANALYZER

Analyzes 26 actual ALGO rallies to extract:
1. Behavioral phases (F1: Uyanış, F2: İlk Hamle, F3: İlk Nefes, F4: Israr, F5: Yorgunluk)
2. Optimal entry/exit zones
3. ALGO-specific patterns (rhythm, harmony, soul)

Philosophy: Read the TRUTH first, build rules later.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies, TRAIN_CUTOFF

class RallyAnatomyAnalyzer:
    """Analyzes individual rally behavioral phases"""
    
    def __init__(self, symbol='ALGOUSDT'):
        self.symbol = symbol
        self.rallies = get_rallies(symbol, tiers=['GOLD', 'SILVER'], train_only=True)
        
        # Load multi-timeframe data
        self.df_15m = self._load_data('15m')
        self.df_1h = self._load_data('1h')
        self.df_4h = self._load_data('4h')
        self.df_1d = self._load_data('1d')
        
        self.rally_analyses = []
    
    def _load_data(self, timeframe):
        """Load and prepare data for given timeframe"""
        path = f"coin_cells/{self.symbol}/data/history_{timeframe}.parquet"
        if not os.path.exists(path):
            return None
        
        df = pd.read_parquet(path)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.sort_values('datetime').reset_index(drop=True)
        
        # Calculate indicators
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(14).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        
        df['is_green'] = df['close'] > df['open']
        df['body_pct'] = abs(df['close'] - df['open']) / df['open'] * 100
        
        return df
    
    def analyze_single_rally(self, rally_date, tier):
        """Analyze behavioral phases of a single rally"""
        
        # Get 15M window: 2 days before rally, rally day, 1 day after
        start = pd.Timestamp(rally_date) - timedelta(days=2)
        end = pd.Timestamp(rally_date) + timedelta(days=1)
        
        mask = (self.df_15m['datetime'] >= start) & (self.df_15m['datetime'] < end)
        df = self.df_15m[mask].copy().reset_index(drop=True)
        
        if len(df) < 50:
            return None
        
        # Mark rally day start
        rally_mask = df['datetime'].dt.date == rally_date
        rally_start_idx = df[rally_mask].index[0] if rally_mask.any() else None
        
        if rally_start_idx is None:
            return None
        
        # Find rally price range
        rally_day_data = df[rally_mask]
        rally_low = rally_day_data['low'].min()
        rally_high = rally_day_data['high'].max()
        rally_range_pct = (rally_high / rally_low - 1) * 100
        
        # Detect phases (simple heuristic for now)
        analysis = {
            'date': rally_date,
            'tier': tier,
            'rally_range_pct': rally_range_pct,
            'rally_start_idx': rally_start_idx,
            'rally_low': rally_low,
            'rally_high': rally_high,
        }
        
        # Phase detection
        pre_rally = df.iloc[:rally_start_idx]
        
        # F1: Uyanış (Volume spike + range expansion in pre-rally)
        if len(pre_rally) >= 20:
            last_20 = pre_rally.iloc[-20:]
            vol_spike = last_20['vol_ratio'].max()
            atr_expansion = last_20['atr'].iloc[-1] / last_20['atr'].iloc[0] if last_20['atr'].iloc[0] > 0 else 1
            
            analysis['f1_vol_spike'] = vol_spike
            analysis['f1_atr_expansion'] = atr_expansion
            analysis['f1_detected'] = vol_spike > 1.5 and atr_expansion > 1.1
        
        # F2: İlk Hamle (First strong green structure)
        rally_first_4h = df.iloc[rally_start_idx:rally_start_idx+16]  # ~4h window
        if len(rally_first_4h) > 0:
            green_ratio = rally_first_4h['is_green'].mean()
            ema_aligned = (rally_first_4h['ema9'] > rally_first_4h['ema21']).mean()
            
            analysis['f2_green_ratio'] = green_ratio
            analysis['f2_ema_aligned'] = ema_aligned
            analysis['f2_detected'] = green_ratio > 0.6 and ema_aligned > 0.7
        
        # F3: İlk Nefes (First pullback)
        # Look for first significant red after F2
        search_window = df.iloc[rally_start_idx:rally_start_idx+32]
        red_candles = search_window[~search_window['is_green']]
        if len(red_candles) > 0:
            first_pullback_idx = red_candles.index[0]
            pullback_depth = (df.loc[first_pullback_idx, 'low'] / df.iloc[rally_start_idx:first_pullback_idx]['high'].max() - 1) * 100
            
            analysis['f3_pullback_depth'] = pullback_depth
            analysis['f3_candles_to_pullback'] = first_pullback_idx - rally_start_idx
            analysis['f3_detected'] = pullback_depth < -1.0  # At least 1% pullback
        
        # F4: Israr (Recovery and new high attempt)
        if 'f3_candles_to_pullback' in analysis:
            post_pullback_idx = first_pullback_idx + 1
            search_high_window = df.iloc[post_pullback_idx:post_pullback_idx+20]
            if len(search_high_window) > 0:
                pre_pullback_high = df.iloc[rally_start_idx:first_pullback_idx]['high'].max()
                post_pullback_high = search_high_window['high'].max()
                
                analysis['f4_new_high_made'] = post_pullback_high > pre_pullback_high
                analysis['f4_recovery_candles'] = len(search_high_window)
        
        # F5: Yorgunluk (Failure to maintain highs)
        rally_day_end = df[rally_mask].index[-1]
        post_rally = df.iloc[rally_day_end+1:rally_day_end+20]
        if len(post_rally) > 5:
            closes_below_rally_high = (post_rally['close'] < rally_high).sum()
            
            analysis['f5_exhaustion_ratio'] = closes_below_rally_high / len(post_rally)
            analysis['f5_detected'] = analysis['f5_exhaustion_ratio'] > 0.7
        
        return analysis
    
    def analyze_all_rallies(self):
        """Analyze all 26 rallies"""
        print(f"🔬 Analyzing {len(self.rallies)} ALGO rallies...")
        print("="*80)
        
        for rally_date, (tier, pct) in self.rallies.items():
            print(f"\n📅 {rally_date} ({tier}, {pct:+.1f}%)")
            
            analysis = self.analyze_single_rally(rally_date, tier)
            
            if analysis:
                self.rally_analyses.append(analysis)
                
                # Print phase summary
                phases = []
                if analysis.get('f1_detected'): phases.append("F1:Uyanış")
                if analysis.get('f2_detected'): phases.append("F2:İlkHamle")
                if analysis.get('f3_detected'): phases.append("F3:İlkNefes")
                if analysis.get('f4_new_high_made'): phases.append("F4:Israr")
                if analysis.get('f5_detected'): phases.append("F5:Yorgunluk")
                
                print(f"   Phases: {' → '.join(phases)}")
                print(f"   Rally Range: {analysis['rally_range_pct']:.1f}%")
                
                if 'f3_pullback_depth' in analysis:
                    print(f"   Pullback: {analysis['f3_pullback_depth']:.1f}% after {analysis['f3_candles_to_pullback']} candles")
            else:
                print("   ⚠️ Insufficient data")
    
    def generate_report(self):
        """Generate comprehensive analysis report"""
        if not self.rally_analyses:
            print("No rally data to analyze")
            return
        
        df_analysis = pd.DataFrame(self.rally_analyses)
        
        print("\n" + "="*80)
        print("📊 ALGO RALLY ANATOMY REPORT")
        print("="*80)
        
        # Phase Detection Stats
        print("\n### PHASE DETECTION STATISTICS:")
        print(f"F1 (Uyanış):      {df_analysis['f1_detected'].sum()}/{len(df_analysis)} ({df_analysis['f1_detected'].mean()*100:.1f}%)")
        print(f"F2 (İlk Hamle):   {df_analysis['f2_detected'].sum()}/{len(df_analysis)} ({df_analysis['f2_detected'].mean()*100:.1f}%)")
        print(f"F3 (İlk Nefes):   {df_analysis['f3_detected'].sum()}/{len(df_analysis)} ({df_analysis['f3_detected'].mean()*100:.1f}%)")
        print(f"F4 (Israr):       {df_analysis['f4_new_high_made'].sum()}/{len(df_analysis)} ({df_analysis['f4_new_high_made'].mean()*100:.1f}%)")
        if 'f5_detected' in df_analysis.columns:
            print(f"F5 (Yorgunluk):   {df_analysis['f5_detected'].sum()}/{len(df_analysis)} ({df_analysis['f5_detected'].mean()*100:.1f}%)")
        
        # Pullback Analysis
        print("\n### PULLBACK (F3) ANALYSIS:")
        pullback_data = df_analysis[df_analysis['f3_detected']]
        if len(pullback_data) > 0:
            print(f"Average Pullback Depth: {pullback_data['f3_pullback_depth'].mean():.2f}%")
            print(f"Median Pullback Depth: {pullback_data['f3_pullback_depth'].median():.2f}%")
            print(f"Avg Candles to Pullback: {pullback_data['f3_candles_to_pullback'].mean():.1f}")
        
        # Entry Zone Recommendation
        print("\n### OPTIMAL ENTRY ZONE (Based on F3→F4 Transition):")
        f3_f4_rallies = df_analysis[df_analysis['f3_detected'] & df_analysis['f4_new_high_made']]
        print(f"Rallies with clear F3→F4: {len(f3_f4_rallies)}/{len(df_analysis)}")
        
        if len(f3_f4_rallies) > 0:
            avg_pullback = f3_f4_rallies['f3_pullback_depth'].mean()
            print(f"Average pullback before recovery: {avg_pullback:.2f}%")
            print(f"💡 ENTRY SIGNAL: Wait for {abs(avg_pullback):.1f}% pullback, then enter on EMA9 reclaim")
        
        # Exit Pattern
        print("\n### EXIT PATTERN (F5 Yorgunluk):")
        if 'f5_detected' in df_analysis.columns:
            print(f"Rallies showing exhaustion: {df_analysis['f5_detected'].sum()}/{len(df_analysis)}")
        
        return df_analysis

def main():
    analyzer = RallyAnatomyAnalyzer('ALGOUSDT')
    analyzer.analyze_all_rallies()
    df_report = analyzer.generate_report()
    
    # Save detailed report
    if df_report is not None:
        report_path = "reports/algo_rally_anatomy.csv"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        df_report.to_csv(report_path, index=False)
        print(f"\n📁 Detailed report saved: {report_path}")

if __name__ == "__main__":
    main()
