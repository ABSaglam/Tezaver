import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class SuperNovaSignal:
    symbol: str
    timestamp: datetime
    mode: str  # 'REVERSAL' or 'MOMENTUM'
    price: float
    volume_ratio: float
    rsi: float
    candle_color: str  # 'GREEN' or 'RED'
    score: float

class SuperNovaDetector:
    """
    Detects SuperNova patterns in two modes:
    1. Panic Reversal (Dönüş): High Volume (>8x) + Low RSI (<30)
    2. Momentum Breakout (Kırılım): Mid Volume (>3x) + High RSI (>60)
    """
    
    def __init__(self):
        self.reversal_vol_threshold = 8.0
        self.reversal_rsi_threshold = 30.0
        
        self.momentum_vol_threshold = 3.0
        self.momentum_rsi_threshold = 60.0
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates necessary technical indicators."""
        df = df.copy()
        
        # 1. Volume Ratio (vs 50-period avg)
        df['avg_vol_50'] = df['volume'].rolling(window=50).mean()
        df['vol_ratio'] = df['volume'] / df['avg_vol_50']
        
        # 2. RSI (14-period)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 3. EMA 50
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 4. Candle Properties
        df['is_green'] = df['close'] > df['open']
        df['body'] = abs(df['close'] - df['open'])
        
        return df

    def detect(self, symbol: str, df: pd.DataFrame, lookback: int = 96) -> List[SuperNovaSignal]:
        """
        Scans only the recent window (for live detection).
        """
        if len(df) < 50:
            return []
            
        df = self.calculate_indicators(df)
        signals = []
        
        # Scan only the requested lookback window
        start_idx = max(50, len(df) - lookback)
        scan_window = df.iloc[start_idx:]
        
        for idx in scan_window.index:
            row = df.loc[idx]
            if pd.isna(row['vol_ratio']) or pd.isna(row['rsi']): continue
                
            # LIVE MODE: Use strict thresholds
            if (row['vol_ratio'] >= self.reversal_vol_threshold and row['rsi'] <= self.reversal_rsi_threshold):
                signals.append(SuperNovaSignal(symbol, row['datetime'], 'REVERSAL', row['close'], row['vol_ratio'], row['rsi'], 'GREEN' if row['is_green'] else 'RED', min(row['vol_ratio']/10,1)*100))
            elif (row['vol_ratio'] >= self.momentum_vol_threshold and row['rsi'] >= self.momentum_rsi_threshold and row['close'] > row['ema_50'] and row['is_green']):
                signals.append(SuperNovaSignal(symbol, row['datetime'], 'MOMENTUM', row['close'], row['vol_ratio'], row['rsi'], 'GREEN', min(row['vol_ratio']/5,1)*100))
                
        return signals

    def analyze_backtest(self, df: pd.DataFrame, lookahead: int = 96) -> List[Dict]:
        """
        Scans logic for Backtest/Inspector.
        Criteria: Volume > 3x (Base filter)
        Returns detailed list with outcome (max gain).
        """
        if len(df) < 50:
            return []
            
        df = self.calculate_indicators(df)
        results = []
        
        # Scan ALL history (skip last lookahead bars as we can't calculate outcome)
        scan_limit = len(df) - lookahead
        
        # Optimized loop: Pre-filter rows with vol > 3x
        # This is strictly for "Volume Spike Analysis" requested by user
        potential_spikes = df[ (df['vol_ratio'] >= 3.0) & (df.index < scan_limit) ].copy()
        
        for idx in potential_spikes.index:
            row = df.loc[idx]
            entry_price = row['close']
            
            # Outcome Calculation
            future_window = df.loc[idx+1 : idx+lookahead]
            if future_window.empty: continue
            
            max_price = future_window['high'].max()
            peak_idx = future_window['high'].idxmax()
            
            max_gain_pct = (max_price - entry_price) / entry_price * 100
            bars_to_peak = peak_idx - idx
            
            # Determine Tier
            if max_gain_pct >= 30: tier = 'DIAMOND'
            elif max_gain_pct >= 20: tier = 'GOLD'
            elif max_gain_pct >= 10: tier = 'SILVER'
            elif max_gain_pct >= 5: tier = 'BRONZE'
            else: tier = 'FAIL'
            
            results.append({
                'datetime': row['datetime'],
                'price': entry_price,
                'vol_ratio': row['vol_ratio'],
                'candle_color': 'GREEN' if row['is_green'] else 'RED',
                'max_gain_pct': max_gain_pct,
                'tier': tier,
                'bars_to_peak': bars_to_peak,
                'peak_price': max_price,
                'peak_time': df.loc[peak_idx, 'datetime']
            })
            
        return results

