import pandas as pd
import numpy as np

class EnergyEngine:
    def __init__(self, profile_data):
        self.profile = profile_data

    def detect_silence(self, df_dict):
        """Silence: Abnormal low volume, neutral momentum, below ATR range."""
        df_4h = df_dict['4h']
        slow_char = self.profile['slow_character'].get('4h', {})
        typical_vol = slow_char.get('typical_volume', 0)
        
        last_vols = df_4h.tail(5)['volume'].mean()
        is_vol_silent = last_vols < (typical_vol * 0.6)
        
        price_std = df_4h.tail(10)['close'].std() / df_4h.tail(10)['close'].mean()
        is_momentum_silent = price_std < 0.005 
        
        return is_vol_silent and is_momentum_silent

    def detect_tension(self, df_dict):
        """Tension: Directional pressure but volume does not confirm, structure holds (Spring effect)."""
        df_15m = df_dict['15m']
        last_5 = df_15m.tail(5)
        price_trend = last_5['close'].diff().sum()
        vol_trend = last_5['volume'].diff().sum()
        
        tension_exists = (abs(price_trend) > 0) and (vol_trend < 0)
        return tension_exists

    def detect_paradox(self, df_dict):
        """Paradox = Silence + Tension simultaneous (CONSTITUTION_RULE)."""
        return self.detect_silence(df_dict) and self.detect_tension(df_dict)
