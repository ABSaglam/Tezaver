import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

class DNAProfileExtractor:
    def __init__(self, base_dir="coin_cells", profile_dir="DNA_Profiles"):
        self.base_dir = Path(base_dir)
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(exist_ok=True)
        self.start_date = pd.Timestamp("2023-01-01", tz="UTC")
        self.end_date = pd.Timestamp("2025-12-31", tz="UTC")
        self.symbols = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    def load_data(self, symbol, timeframe):
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists():
            return None
        df = pd.read_parquet(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        # Isolate training data (2023-2025)
        df = df[(df['datetime'] >= self.start_date) & (df['datetime'] <= self.end_date)]
        return df

    def find_expansion_days(self, df_1d):
        """Identifies days where High or Close >= +10% from previous Close."""
        if df_1d is None or len(df_1d) < 2:
            return []
        
        # Calculation relative to previous close
        df_1d['prev_close'] = df_1d['close'].shift(1)
        # We look for expansion from prev close to current high
        df_1d['exp_ratio'] = (df_1d['high'] / df_1d['prev_close']) - 1
        
        expansion_days = df_1d[df_1d['exp_ratio'] >= 0.10].copy()
        return expansion_days

    def extract_dna_window(self, df_dict, expansion_date, window_size=7):
        """Extracts windows of data before the expansion day."""
        dna_snapshot = {}
        
        for tf, df in df_dict.items():
            if df is None: continue
            
            cutoff = expansion_date
            # Ensure enough data for ATR(14)
            pre_window = df[df['datetime'] < cutoff].tail(40 * (24 if tf == '1h' else 1)) # Increased padding
            
            if len(pre_window) < 20: continue
            
            # Use all available data in window for ATR to avoid NaNs
            atr_series = (pre_window['high'] - pre_window['low']).rolling(min(14, len(pre_window))).mean()
            if atr_series.empty or pd.isna(atr_series.iloc[-1]): continue
            
            atr = atr_series.iloc[-1]
            norm_atr = atr / pre_window['close'].iloc[-1]
            
            avg_vol = pre_window['volume'].mean()
            recent_vol = pre_window['volume'].tail(3).mean()
            vol_contraction = recent_vol / (avg_vol + 1e-9)
            
            dna_snapshot[tf] = {
                "norm_atr": float(norm_atr),
                "vol_contraction": float(vol_contraction),
                "price_std": float(pre_window['close'].std() / (pre_window['close'].mean() + 1e-9))
            }
            
        return dna_snapshot

    def process_symbol(self, symbol):
        df_1d = self.load_data(symbol, '1d')
        if df_1d is None: return None
        
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
                dna_profiles.append({
                    "expansion_date": date.isoformat(),
                    "expansion_ratio": row['exp_ratio'],
                    "dna": snapshot
                })
        
        # Average DNA for the coin
        return dna_profiles

    def run(self, limit=None):
        target_symbols = self.symbols[:limit] if limit else self.symbols
        all_dna_manifest = {}
        
        print(f"Extracting DNA profiles for {len(target_symbols)} symbols (2023-2025)...")
        for symbol in tqdm(target_symbols):
            profiles = self.process_symbol(symbol)
            if profiles:
                all_dna_manifest[symbol] = profiles
                
        with open(self.profile_dir / "coin_DNA_profile.json", "w") as f:
            json.dump(all_dna_manifest, f, indent=4)
            
        print(f"DNA extraction complete. Profiles saved for {len(all_dna_manifest)} coins.")

if __name__ == "__main__":
    extractor = DNAProfileExtractor()
    extractor.run(limit=50) # Start with 50 coins for testing
