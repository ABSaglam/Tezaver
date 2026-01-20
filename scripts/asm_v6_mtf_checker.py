#!/usr/bin/env python3
"""
ASM v6 - Phase 2: Multi-Timeframe Checker

Checks 1H/4H EMA alignment for multi-timeframe confirmation
Reduces false positives by requiring higher TF agreement
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class MTFChecker:
    """Multi-Timeframe confirmation checker"""
    
    def __init__(self, symbol='ALGOUSDT'):
        self.symbol = symbol
        self.h1_data = None
        self.h4_data = None
        self._load_data()
    
    def _load_data(self):
        """Load 1H and 4H data"""
        try:
            # Load 1H
            h1_path = f"coin_cells/{self.symbol}/data/history_1h.parquet"
            self.h1_data = pd.read_parquet(h1_path)
            self.h1_data['datetime'] = pd.to_datetime(self.h1_data['timestamp'], unit='ms')
            self._calc_indicators(self.h1_data)
            
            # Load 4H
            h4_path = f"coin_cells/{self.symbol}/data/history_4h.parquet"
            self.h4_data = pd.read_parquet(h4_path)
            self.h4_data['datetime'] = pd.to_datetime(self.h4_data['timestamp'], unit='ms')
            self._calc_indicators(self.h4_data)
            
        except FileNotFoundError as e:
            print(f"⚠️ Warning: Could not load MTF data: {e}")
    
    def _calc_indicators(self, df):
        """Calculate EMAs for dataframe"""
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
    
    def check_ema_alignment(self, df, timestamp):
        """Check if EMA9 > EMA21 > EMA50 at given timestamp"""
        if df is None or len(df) == 0:
            return False, "No data"
        
        # Find nearest candle to timestamp
        ts = pd.Timestamp(timestamp)
        df_filtered = df[df['datetime'] <= ts]
        
        if len(df_filtered) == 0:
            return False, "No candle before timestamp"
        
        latest = df_filtered.iloc[-1]
        
        # Check alignment
        aligned = (latest['ema9'] > latest['ema21'] > latest['ema50'])
        
        details = {
            'ema9': latest['ema9'],
            'ema21': latest['ema21'],
            'ema50': latest['ema50'],
            'aligned': aligned,
            'candle_time': latest['datetime']
        }
        
        return aligned, details
    
    def get_mtf_confirmation(self, timestamp_15m, require_both=False):
        """
        Get multi-timeframe confirmation
        
        Args:
            timestamp_15m: 15M candle timestamp
            require_both: If True, both 1H and 4H must align. If False, either is OK.
        
        Returns:
            dict with confirmation status and details
        """
        result = {
            'timestamp_15m': timestamp_15m,
            'h1_aligned': False,
            'h4_aligned': False,
            'confirmed': False,
            'confidence': 'LOW',
            'details': {}
        }
        
        # Check 1H
        h1_aligned, h1_details = self.check_ema_alignment(self.h1_data, timestamp_15m)
        result['h1_aligned'] = h1_aligned
        result['details']['h1'] = h1_details
        
        # Check 4H
        h4_aligned, h4_details = self.check_ema_alignment(self.h4_data, timestamp_15m)
        result['h4_aligned'] = h4_aligned
        result['details']['h4'] = h4_details
        
        # Determine confirmation
        if require_both:
            result['confirmed'] = h1_aligned and h4_aligned
            if result['confirmed']:
                result['confidence'] = 'VERY_HIGH'
            elif h1_aligned or h4_aligned:
                result['confidence'] = 'MEDIUM'
            else:
                result['confidence'] = 'LOW'
        else:
            result['confirmed'] = h1_aligned or h4_aligned
            if h1_aligned and h4_aligned:
                result['confidence'] = 'VERY_HIGH'
            elif h1_aligned or h4_aligned:
                result['confidence'] = 'HIGH'
            else:
                result['confidence'] = 'LOW'
        
        return result

def test_mtf_checker():
    """Test MTF checker on known dates"""
    checker = MTFChecker('ALGOUSDT')
    
    # Test dates from rally soul
    test_dates = [
        '2023-02-01T19:45:00',  # Successful rally
        '2023-03-14T16:15:00',  # Another successful rally
        '2023-01-13T09:00:00',  # Failed entry
    ]
    
    print("🧪 Testing MTF Checker")
    print("="*80)
    
    for ts in test_dates:
        print(f"\n📅 Testing: {ts}")
        result = checker.get_mtf_confirmation(ts, require_both=False)
        
        print(f"  1H Aligned: {result['h1_aligned']}")
        print(f"  4H Aligned: {result['h4_aligned']}")
        print(f"  Confirmed: {result['confirmed']}")
        print(f"  Confidence: {result['confidence']}")

if __name__ == "__main__":
    test_mtf_checker()
    print("\n✅ Phase 2 Complete!")
