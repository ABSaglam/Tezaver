"""
Tezaver Rally Analyzer (The Scout) - M25
========================================

This module implements the IAnalyzer interface.
It scans market data windows to detect 'Rally' events (significant price increases from local lows).
It uses the 'Oracle Mode' logic (Rolling Window Extrema) adapted for the Unified Engine.
"""

from typing import List, Any
import pandas as pd
from datetime import datetime

from tezaver.engine.interfaces import IAnalyzer, MarketSignal

class RallyAnalyzer(IAnalyzer):
    def __init__(self, rally_threshold: float = 0.02, lookback_window: int = 50):
        """
        Args:
            rally_threshold: Percentage gain needed to trigger signal (e.g., 0.02 for 2%)
            lookback_window: Number of bars to look back for local minimum.
        """
        self.rally_threshold = rally_threshold
        self.lookback_window = lookback_window
        
    def analyze(self, symbol: str, timeframe: str, data: Any) -> List[MarketSignal]:
        """
        Analyze a DataFrame slice to find if a Rally Start signal just happened.
        
        Args:
            data: pandas DataFrame containing 'close', 'high', 'low' columns.
                  Must contain at least 'lookback_window' rows.
        """
        signals = []
        df = data
        
        # Validation
        if df is None or len(df) < self.lookback_window:
            return []
            
        # Enhanced Oracle Logic for "Real-time" / "Replay" tick
        # We only care if the condition is met *at the latest bar* 
        # to avoid repeating signals for the same rally.
        
        current_bar = df.iloc[-1]
        current_price = current_bar['close']
        current_time = current_bar.name # Assuming DateTimeIndex
        
        # 1. Find the lowest low in the lookback window
        window = df.iloc[-self.lookback_window:]
        min_price = window['low'].min()
        
        # 2. Calculate gain from low
        gain_pct = (current_price - min_price) / min_price
        
        # 3. Check Threshold
        # DEBUG PRINT
        # print(f"DEBUG: {symbol} {current_time} Gain: {gain_pct:.4f} Thresh: {self.rally_threshold}")
        
        if gain_pct >= self.rally_threshold:
            # 4. EDGE DETECTION: Did we JUST cross the threshold?
            
            prev_bar = df.iloc[-2]
            # Use the SAME min_price for fair comparison or re-calculate? 
            # Strictly, we should re-calc prev min, but usually it's stable.
            # Let's simplify: simply check if prev close was below threshold relative to ITS OWN window?
            # No, that's expensive. Let's use current min_price approximation.
            
            prev_gain_pct = (prev_bar['close'] - min_price) / min_price
            
            is_new_breakout = prev_gain_pct < self.rally_threshold
            
            # DEBUG
            # if is_new_breakout:
            #    print(f"!!! SIGNAL {symbol} {current_time} !!!")
            
            if is_new_breakout:
                signal: MarketSignal = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_type": "RALLY_START",
                    "timestamp": current_time if isinstance(current_time, datetime) else datetime.now(),
                    # Score is now relative to threshold.
                    # If gain == threshold -> Score 50 (Pass).
                    # If gain == 2*threshold -> Score 100 (Max).
                    "score": min((gain_pct / self.rally_threshold) * 50.0, 100.0),
                    "metadata": {
                        "current_price": current_price,
                        "rally_low": min_price,
                        "gain_pct": gain_pct
                    }
                }
                signals.append(signal)
                
        return signals
