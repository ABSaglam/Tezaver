import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

class DNARollingExtractor:
    def __init__(self, base_dir="coin_cells", profile_dir="DNA_Profiles"):
        self.base_dir = Path(base_dir)
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(exist_ok=True)
        self.start_date = pd.Timestamp("2023-01-01", tz="UTC")
        self.end_date = pd.Timestamp("2025-12-31", tz="UTC")
        # Define the "Recent" window for weighting (Last 12 months of training)
        self.recent_threshold = pd.Timestamp("2025-01-01", tz="UTC")
        self.symbols = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    def load_data(self, symbol, timeframe):
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists(): return None
        df = pd.read_parquet(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        # Isolate training data (2023-2025)
        df = df[(df['datetime'] >= self.start_date) & (df['datetime'] <= self.end_date)]
        return df

    def find_expansion_days(self, df_1d):
        if df_1d is None or len(df_1d) < 2: return []
        df_1d = df_1d.copy()
        df_1d['prev_close'] = df_1d['close'].shift(1)
        df_1d['exp_ratio'] = (df_1d['high'] / df_1d['prev_close']) - 1
        return df_1d[df_1d['exp_ratio'] >= 0.10].copy()

    def extract_dna_window(self, df_dict, expansion_date):
        dna_snapshot = {}
        cutoff = expansion_date
        
        for tf, df in df_dict.items():
            if df is None: continue
            
            # 50 session window for metrics safety (EMA/ATR)
            pre_window = df[df['datetime'] < cutoff].tail(50 * (24 if tf == '1h' else 1))
            if len(pre_window) < 30: continue
            
            # A. Structural DNA
            atr_series = (pre_window['high'] - pre_window['low']).rolling(14).mean()
            if atr_series.empty or pd.isna(atr_series.iloc[-1]): continue
            norm_atr = float(atr_series.iloc[-1] / pre_window['close'].iloc[-1])
            
            ranges = (pre_window['high'] - pre_window['low']).tail(5)
            slope = float(np.polyfit(range(len(ranges)), ranges, 1)[0] / (ranges.mean() + 1e-9))
            
            ema20 = pre_window['close'].ewm(span=20).mean()
            ema_dist = float(abs(pre_window['close'].iloc[-1] - ema20.iloc[-1]) / (ema20.iloc[-1] + 1e-9))
            
            # B. Energy DNA
            avg_vol = pre_window['volume'].mean()
            recent_vol = pre_window['volume'].tail(3).mean()
            vol_contraction = float(recent_vol / (avg_vol + 1e-9))
            
            volt_ratio = float(atr_series.iloc[-1] / (atr_series.iloc[-14:-1].mean() + 1e-9))
            
            # C. Behavioral (Wick tolerance & Price STD)
            wicks = (pre_window['high'] - pre_window[['open','close']].max(axis=1)).mean()
            wick_ratio = float(wicks / (pre_window['high'] - pre_window['low']).mean())
            
            dna_snapshot[tf] = {
                "norm_atr": norm_atr,
                "range_slope": slope,
                "ema_dist": ema_dist,
                "vol_contraction": vol_contraction,
                "volt_ratio": volt_ratio,
                "wick_ratio": wick_ratio,
                "price_std": float(pre_window['close'].std() / (pre_window['close'].mean() + 1e-9))
            }
            
        return dna_snapshot

    def process_symbol(self, symbol):
        df_1d = self.load_data(symbol, '1d')
        if df_1d is None or len(df_1d) < 50: return None
        
        exp_days = self.find_expansion_days(df_1d)
        if len(exp_days) == 0: return None
        
        df_dict = {
            '1d': df_1d,
            '4h': self.load_data(symbol, '4h'),
            '1h': self.load_data(symbol, '1h')
        }
        
        dna_profiles = []
        for _, row in exp_days.iterrows():
            date = row['datetime']
            snapshot = self.extract_dna_window(df_dict, date)
            if snapshot:
                # Rolling weight logic
                # 2025 (Last 12m) -> 0.6 weight
                # Prior -> 0.4 weight
                weight = 0.6 if date >= self.recent_threshold else 0.4
                
                dna_profiles.append({
                    "expansion_date": date.isoformat(),
                    "expansion_ratio": float(row['exp_ratio']),
                    "weight": weight,
                    "dna": snapshot
                })
        
        return dna_profiles

    def run(self, limit=None):
        target_symbols = self.symbols[:limit] if limit else self.symbols
        rolling_manifest = {}
        
        print(f"Extracting ROLLING DNA profiles for {len(target_symbols)} symbols (2023-2025)...")
        for symbol in tqdm(target_symbols):
            try:
                profiles = self.process_symbol(symbol)
                if profiles:
                    rolling_manifest[symbol] = profiles
            except Exception:
                continue
                
        with open(self.profile_dir / "rolling_DNA_profile.json", "w") as f:
            json.dump(rolling_manifest, f, indent=4)
            
        print(f"Rolling DNA extraction complete. Profiles saved for {len(rolling_manifest)} coins.")

if __name__ == "__main__":
    extractor = DNARollingExtractor()
    extractor.run() # Start with full universe
