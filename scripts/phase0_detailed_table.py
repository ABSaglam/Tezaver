#!/usr/bin/env python3
"""
🔬 PHASE-0: DETAILED RALLY PHASE TABLE GENERATOR

Creates granular phase-by-phase table for ALGO rallies:
- Exact candle boundaries for F1-F5
- Indicator states per phase
- Behavioral notes

Output: CSV table ready for ASM training
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies, TRAIN_CUTOFF

class DetailedPhaseAnalyzer:
    """Detailed phase-by-phase rally analyzer"""
    
    def __init__(self, symbol='ALGOUSDT'):
        self.symbol = symbol
        # Focus on GOLD rallies first (highest quality), then add SILVER
        self.rallies = get_rallies(symbol, tiers=['GOLD', 'SILVER'], train_only=True)
        
        # Load 15M data
        path = f"coin_cells/{symbol}/data/history_15m.parquet"
        self.df = pd.read_parquet(path)
        self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
        self.df = self.df.sort_values('datetime').reset_index(drop=True)
        
        # Calculate indicators
        self._calc_indicators()
        
        self.phase_table = []
    
    def _calc_indicators(self):
        """Calculate all necessary indicators"""
        df = self.df
        
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
        df['atr_ma'] = df['atr'].rolling(50).mean()
        df['atr_ratio'] = df['atr'] / df['atr_ma']
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        
        df['is_green'] = df['close'] > df['open']
    
    def _check_ema_alignment(self, idx):
        """Check if EMA9 > EMA21 > EMA50"""
        row = self.df.iloc[idx]
        return row['ema9'] > row['ema21'] > row['ema50']
    
    def _get_vol_direction(self, start_idx, end_idx):
        """Get volume direction for phase"""
        if start_idx >= end_idx:
            return "→"
        vol_start = self.df.iloc[start_idx]['vol_ratio']
        vol_end = self.df.iloc[end_idx]['vol_ratio']
        if vol_end > vol_start * 1.1:
            return "↑"
        elif vol_end < vol_start * 0.9:
            return "↓"
        return "→"
    
    def analyze_rally_phases(self, rally_date, tier, rally_num):
        """Analyze phases for a single rally with detailed breakdown"""
        
        # Get rally window
        start = pd.Timestamp(rally_date) - timedelta(days=1)
        end = pd.Timestamp(rally_date) + timedelta(days=1)
        
        mask = (self.df['datetime'] >= start) & (self.df['datetime'] < end)
        rally_df = self.df[mask].copy().reset_index()
        
        if len(rally_df) < 20:
            return []
        
        # Find rally day start
        rally_day_mask = rally_df['datetime'].dt.date == rally_date
        rally_start_idx = rally_df[rally_day_mask].index[0] if rally_day_mask.any() else None
        
        if rally_start_idx is None or rally_start_idx < 10:
            return []
        
        phases = []
        candle_counter = 0  # Relative candle numbering
        
        # Detect phases backwards from rally start
        pre_rally = rally_df.iloc[max(0, rally_start_idx-20):rally_start_idx]
        rally_window = rally_df.iloc[rally_start_idx:min(len(rally_df), rally_start_idx+40)]
        
        # F1: UYANIŞ (Last 5-10 candles before rally with volume spike)
        f1_candidates = pre_rally.iloc[-10:]
        vol_spike_idx = f1_candidates['vol_ratio'].idxmax()
        f1_start = max(0, vol_spike_idx - 2)
        f1_end = rally_start_idx - 1
        
        if f1_end > f1_start and f1_candidates.loc[vol_spike_idx, 'vol_ratio'] > 1.3:
            f1_data = rally_df.loc[f1_start]
            phases.append({
                'rally_num': rally_num,
                'date': rally_date,
                'tier': tier,
                'phase': 'F1',
                'start_candle': candle_counter,
                'end_candle': candle_counter + (f1_end - f1_start),
                'ema_aligned': '✅' if self._check_ema_alignment(f1_data['index']) else '❌',
                'atr_ratio': f"{f1_data['atr_ratio']:.2f}" if not pd.isna(f1_data['atr_ratio']) else "N/A",
                'rsi': f"{f1_data['rsi']:.0f}" if not pd.isna(f1_data['rsi']) else "N/A",
                'vol_dir': self._get_vol_direction(f1_start, f1_end),
                'notes': f"Uyanış: Hacim artışı {f1_data['vol_ratio']:.1f}x"
            })
            candle_counter += (f1_end - f1_start) + 1
        
        # F2: İLK HAMLE (First 4-8 candles of rally with strong greens)
        f2_start = rally_start_idx
        f2_window = rally_window.iloc[:8]
        green_ratio = f2_window['is_green'].mean()
        
        if green_ratio > 0.6:
            f2_end = rally_start_idx + len(f2_window) - 1
            f2_data = rally_df.loc[f2_start]
            phases.append({
                'rally_num': rally_num,
                'date': rally_date,
                'tier': tier,
                'phase': 'F2',
                'start_candle': candle_counter,
                'end_candle': candle_counter + len(f2_window) - 1,
                'ema_aligned': '✅' if self._check_ema_alignment(f2_data['index']) else '❌',
                'atr_ratio': f"{f2_data['atr_ratio']:.2f}" if not pd.isna(f2_data['atr_ratio']) else "N/A",
                'rsi': f"{f2_data['rsi']:.0f}" if not pd.isna(f2_data['rsi']) else "N/A",
                'vol_dir': self._get_vol_direction(f2_start, f2_end),
                'notes': f"İlk Hamle: {green_ratio*100:.0f}% yeşil mum"
            })
            candle_counter += len(f2_window)
            
            # F3: İLK NEFES (First pullback after F2)
            post_f2 = rally_window.iloc[8:20]
            red_candles = post_f2[~post_f2['is_green']]
            
            if len(red_candles) > 0:
                f3_start_idx = red_candles.index[0]
                # Find extent of pullback (until EMA9 reclaim or 3 candles max)
                f3_end_idx = min(f3_start_idx + 3, len(rally_df)-1)
                
                f3_data = rally_df.loc[f3_start_idx]
                high_before = rally_window.iloc[:8]['high'].max()
                low_pullback = rally_df.loc[f3_start_idx:f3_end_idx, 'low'].min()
                pullback_pct = (low_pullback / high_before - 1) * 100
                
                phases.append({
                    'rally_num': rally_num,
                    'date': rally_date,
                    'tier': tier,
                    'phase': 'F3',
                    'start_candle': candle_counter,
                    'end_candle': candle_counter + (f3_end_idx - f3_start_idx),
                    'ema_aligned': '✅' if self._check_ema_alignment(f3_data['index']) else '❌',
                    'atr_ratio': f"{f3_data['atr_ratio']:.2f}" if not pd.isna(f3_data['atr_ratio']) else "N/A",
                    'rsi': f"{f3_data['rsi']:.0f}" if not pd.isna(f3_data['rsi']) else "N/A",
                    'vol_dir': self._get_vol_direction(f3_start_idx, f3_end_idx),
                    'notes': f"İlk Nefes: {pullback_pct:.1f}% geri çekilme"
                })
                candle_counter += (f3_end_idx - f3_start_idx) + 1
                
                # F4: ISRAR (Recovery and new high attempt)
                f4_start_idx = f3_end_idx + 1
                f4_window = rally_df.loc[f4_start_idx:min(f4_start_idx+10, len(rally_df)-1)]
                
                if len(f4_window) > 0:
                    post_high = f4_window['high'].max()
                    new_high_made = post_high > high_before
                    
                    if new_high_made:
                        f4_end_idx = f4_window['high'].idxmax()
                        f4_data = rally_df.loc[f4_start_idx]
                        
                        phases.append({
                            'rally_num': rally_num,
                            'date': rally_date,
                            'tier': tier,
                            'phase': 'F4',
                            'start_candle': candle_counter,
                            'end_candle': candle_counter + (f4_end_idx - f4_start_idx),
                            'ema_aligned': '✅' if self._check_ema_alignment(f4_data['index']) else '❌',
                            'atr_ratio': f"{f4_data['atr_ratio']:.2f}" if not pd.isna(f4_data['atr_ratio']) else "N/A",
                            'rsi': f"{f4_data['rsi']:.0f}" if not pd.isna(f4_data['rsi']) else "N/A",
                            'vol_dir': self._get_vol_direction(f4_start_idx, f4_end_idx),
                            'notes': f"Israr: Yeni high {post_high:.4f}"
                        })
                        candle_counter += (f4_end_idx - f4_start_idx) + 1
                        
                        # F5: YORGUNLUK (Failure to maintain highs)
                        f5_start_idx = f4_end_idx + 1
                        f5_window = rally_df.loc[f5_start_idx:min(f5_start_idx+10, len(rally_df)-1)]
                        
                        if len(f5_window) > 3:
                            closes_below = (f5_window['close'] < post_high).sum()
                            if closes_below / len(f5_window) > 0.7:
                                f5_end_idx = f5_start_idx + len(f5_window) - 1
                                f5_data = rally_df.loc[f5_start_idx]
                                
                                phases.append({
                                    'rally_num': rally_num,
                                    'date': rally_date,
                                    'tier': tier,
                                    'phase': 'F5',
                                    'start_candle': candle_counter,
                                    'end_candle': candle_counter + len(f5_window) - 1,
                                    'ema_aligned': '✅' if self._check_ema_alignment(f5_data['index']) else '❌',
                                    'atr_ratio': f"{f5_data['atr_ratio']:.2f}" if not pd.isna(f5_data['atr_ratio']) else "N/A",
                                    'rsi': f"{f5_data['rsi']:.0f}" if not pd.isna(f5_data['rsi']) else "N/A",
                                    'vol_dir': self._get_vol_direction(f5_start_idx, f5_end_idx),
                                    'notes': f"Yorgunluk: {closes_below}/{len(f5_window)} mum tepe altı"
                                })
        
        return phases
    
    def analyze_all_rallies(self, max_rallies=26):
        """Analyze detailed phases for top N rallies"""
        print(f"🔬 Detailed Phase Analysis: Top {max_rallies} ALGO Rallies")
        print("="*80)
        
        rally_num = 1
        for rally_date, (tier, pct) in list(self.rallies.items())[:max_rallies]:
            print(f"\n📅 Rally #{rally_num}: {rally_date} ({tier}, {pct:+.1f}%)")
            
            phases = self.analyze_rally_phases(rally_date, tier, rally_num)
            
            if phases:
                self.phase_table.extend(phases)
                print(f"   Detected {len(phases)} phases:")
                for p in phases:
                    print(f"   └─ {p['phase']}: Candles {p['start_candle']}-{p['end_candle']} | RSI {p['rsi']} | Vol {p['vol_dir']}")
            else:
                print("   ⚠️ No clear phases detected")
            
            rally_num += 1
    
    def generate_table(self):
        """Generate final table"""
        if not self.phase_table:
            print("\n❌ No phase data to generate table")
            return None
        
        df = pd.DataFrame(self.phase_table)
        
        # Reorder columns
        df = df[['rally_num', 'date', 'tier', 'phase', 'start_candle', 'end_candle', 
                 'ema_aligned', 'atr_ratio', 'rsi', 'vol_dir', 'notes']]
        
        # Rename for clarity
        df.columns = ['Ralli', 'Tarih', 'Tier', 'Faz', 'Baş_Mum', 'Bit_Mum', 
                      'EMA9>21>50', 'ATR/ATR_MA', 'RSI', 'Hacim', 'Notlar']
        
        return df

def main():
    analyzer = DetailedPhaseAnalyzer('ALGOUSDT')
    analyzer.analyze_all_rallies(max_rallies=26)
    
    df_table = analyzer.generate_table()
    
    if df_table is not None:
        print("\n" + "="*80)
        print("📊 PHASE TABLE PREVIEW (First 20 rows):")
        print("="*80)
        print(df_table.head(20).to_string(index=False))
        
        # Save
        output_path = "reports/algo_rally_phase_table.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_table.to_csv(output_path, index=False)
        print(f"\n📁 Full table saved: {output_path}")
        print(f"   Total phase entries: {len(df_table)}")

if __name__ == "__main__":
    main()
