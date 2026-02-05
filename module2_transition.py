import pandas as pd
import numpy as np

class TransitionEngine:
    def __init__(self):
        pass

    def is_1d_neutral(self, df):
        """1D: directionally neutral / indecisive (Small bodies, indecision)."""
        last_3 = df.tail(3)
        avg_body = (last_3['close'] - last_3['open']).abs().mean()
        avg_range = (last_3['high'] - last_3['low']).mean()
        return (avg_body / avg_range) < 0.35

    def is_4h_boundary(self, df):
        """4H: structural compression or boundary condition."""
        last_20 = df.tail(20)
        std = last_20['close'].std()
        avg = last_20['close'].mean()
        return (std / avg) < 0.015 

    def is_1h_rhythm_instability(self, df):
        """1H: rhythm instability (change in pace)."""
        last_5 = df.tail(5)
        vols = last_5['volume']
        return vols.std() / (vols.mean() + 1e-9) > 0.5

    def is_15m_breath(self, df):
        """15m: micro-expansion or first 'breath'."""
        last_candle = df.iloc[-1]
        prev_candles = df.iloc[-5:-1]
        avg_prev_range = (prev_candles['high'] - prev_candles['low']).mean()
        current_range = last_candle['high'] - last_candle['low']
        return current_range > (1.5 * avg_prev_range)

    def detect_transition(self, symbol, df_dict):
        """Narrative alignment: 1D Neutral + 4H Boundary + 1H Change + 15m Breath."""
        results = {
            "1d_neutral": self.is_1d_neutral(df_dict['1d']),
            "4h_boundary": self.is_4h_boundary(df_dict['4h']),
            "1h_instability": self.is_1h_rhythm_instability(df_dict['1h']),
            "15m_breath": self.is_15m_breath(df_dict['15m'])
        }
        
        positive_count = sum(results.values())
        return {
            "is_transition": positive_count >= 3,
            "tf_results": results,
            "confidence_flags": positive_count
        }
