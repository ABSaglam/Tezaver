import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
from pathlib import Path

class CoinProfilingSystem:
    def __init__(self, base_dir="coin_cells"):
        self.base_dir = Path(base_dir)
        self.profiles_dir = Path("character_profiles")
        self.profiles_dir.mkdir(exist_ok=True)

    def load_data(self, symbol, timeframe):
        """Loads parquet data for a specific symbol and timeframe."""
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists():
            return None
        return pd.read_parquet(file_path)

    def calculate_atr(self, df, period=14):
        """Calculates ATR safely."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()

    def generate_slow_character(self, df_dict):
        """
        Computes Slow Character (6-12 months rolling).
        """
        slow_profile = {}
        for tf, df in df_dict.items():
            if df is None or len(df) < 100: continue
            
            # Focused on structural fingerprints
            window = min(len(df), 365)
            df_window = df.iloc[-window:]
            
            atr = self.calculate_atr(df_window)
            norm_atr = atr / df_window['close']
            
            slow_profile[tf] = {
                "avg_norm_atr": norm_atr.mean(),
                "std_norm_atr": norm_atr.std(),
                "typical_volume": df_window['volume'].median(),
                "vola_compression_tolerance": (df_window['high'] - df_window['low']).rolling(20).min().mean() / df_window['close'].mean()
            }
        return slow_profile

    def generate_fast_drift(self, df_dict):
        """
        Computes Fast Drift (30-60 days rolling).
        """
        fast_profile = {}
        for tf, df in df_dict.items():
            if df is None or len(df) < 40: continue
            
            window = 60
            df_window = df.iloc[-window:]
            
            atr = self.calculate_atr(df_window)
            norm_atr = atr / df_window['close']
            
            fast_profile[tf] = {
                "recent_vola_avg": norm_atr.mean(),
                "recent_volume_avg": df_window['volume'].mean(),
                "momentum_drift": (df_window['close'].iloc[-1] / df_window['close'].iloc[0]) - 1
            }
        return fast_profile

    def build_profile(self, symbol):
        """Builds and stores the character profile for a coin."""
        timeframes = ["15m", "1h", "4h", "1d", "1w"]
        df_dict = {}
        for tf in timeframes:
            df_dict[tf] = self.load_data(symbol, tf)
            
        slow = self.generate_slow_character(df_dict)
        fast = self.generate_fast_drift(df_dict)
        
        profile = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "slow_character": slow,
            "fast_drift": fast
        }
        
        profile_path = self.profiles_dir / f"{symbol}_profile.json"
        with open(profile_path, 'w') as f:
            json.dump(profile, f, indent=4)
        
        return profile

if __name__ == "__main__":
    profiler = CoinProfilingSystem()
    profile = profiler.build_profile("BTCUSDT")
    print(f"Profile hardened for BTCUSDT: {profile['timestamp']}")
