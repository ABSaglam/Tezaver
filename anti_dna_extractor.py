import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from tqdm import tqdm
import random

class AntiDNAExtractor:
    def __init__(self, base_dir="coin_cells", profile_dir="DNA_Profiles"):
        self.base_dir = Path(base_dir)
        self.profile_dir = Path(profile_dir)
        self.start_date = pd.Timestamp("2023-01-01", tz="UTC")
        self.end_date = pd.Timestamp("2025-12-31", tz="UTC")
        self.symbols = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    def load_data(self, symbol, timeframe):
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists():
            return None
        df = pd.read_parquet(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df[(df['datetime'] >= self.start_date) & (df['datetime'] <= self.end_date)]
        return df

    def find_anti_days(self, df_1d, exp_dates):
        """Finds days where NO move >= 10% happened in the next day, but it was in compression."""
        if df_1d is None or len(df_1d) < 10:
            return []
        
        # Define compression: ATR below median
        df_1d['atr'] = (df_1d['high'] - df_1d['low']).rolling(14).mean()
        median_atr = df_1d['atr'].median()
        
        # Next day move
        df_1d['next_high_ratio'] = (df_1d['high'].shift(-1) / df_1d['close']) - 1
        
        # Potential Anti-DNA days: Compression AND Not an expansion AND Not near an existing expansion
        anti_candidates = df_1d[
            (df_1d['atr'] < (median_atr * 1.1)) & 
            (df_1d['next_high_ratio'] < 0.05) & 
            (~df_1d['datetime'].isin(exp_dates))
        ].copy()
        
        if len(anti_candidates) == 0:
            return []
            
        # Sample an equal number of Anti-DNA to DNA (if possible)
        num_to_sample = min(len(anti_candidates), len(exp_dates))
        if num_to_sample == 0: num_to_sample = min(len(anti_candidates), 5)
        
        sampled = anti_candidates.sample(n=num_to_sample)
        return sampled

    def extract_dna_window(self, df_dict, target_date, window_size=7):
        """Enhanced Anti-DNA window extraction."""
        dna_snapshot = {}
        cutoff = target_date
        
        for tf, df in df_dict.items():
            if df is None: continue
            
            pre_window = df[df['datetime'] < cutoff].tail(50 * (24 if tf == '1h' else 1))
            if len(pre_window) < 30: continue
            
            atr_series = (pre_window['high'] - pre_window['low']).rolling(min(14, len(pre_window))).mean()
            if atr_series.empty or pd.isna(atr_series.iloc[-1]): continue
            norm_atr = float(atr_series.iloc[-1] / pre_window['close'].iloc[-1])
            
            ranges = (pre_window['high'] - pre_window['low']).tail(5)
            slope = float(np.polyfit(range(len(ranges)), ranges, 1)[0] / (ranges.mean() + 1e-9))
            
            ema20 = pre_window['close'].ewm(span=20).mean()
            ema_dist = float(abs(pre_window['close'].iloc[-1] - ema20.iloc[-1]) / (ema20.iloc[-1] + 1e-9))
            
            avg_vol = pre_window['volume'].mean()
            recent_vol = pre_window['volume'].tail(3).mean()
            vol_contraction = float(recent_vol / (avg_vol + 1e-9))
            
            volt_ratio = float(atr_series.iloc[-1] / (atr_series.iloc[-14:-1].mean() + 1e-9))
            
            dna_snapshot[tf] = {
                "norm_atr": norm_atr,
                "range_slope": slope,
                "ema_dist": ema_dist,
                "vol_contraction": vol_contraction,
                "volt_ratio": volt_ratio,
                "price_std": float(pre_window['close'].std() / (pre_window['close'].mean() + 1e-9))
            }
        return dna_snapshot

    def run(self, limit=None):
        # Load existing DNA profiles to know how many to sample and which dates to avoid
        with open(self.profile_dir / "coin_DNA_profile.json", "r") as f:
            dna_manifest = json.load(f)
            
        anti_manifest = {}
        target_symbols = list(dna_manifest.keys())[:limit] if limit else list(dna_manifest.keys())
        
        print(f"Extracting GLOBAL Anti-DNA profiles for {len(target_symbols)} symbols (2023-2025)...")
        for symbol in tqdm(target_symbols):
            try:
                df_1d = self.load_data(symbol, '1d')
                if df_1d is None: continue
                
                exp_dates = [pd.to_datetime(d['expansion_date']) for d in dna_manifest[symbol]]
                anti_days = self.find_anti_days(df_1d, exp_dates)
                
                if len(anti_days) == 0: continue
                
                df_dict = {
                    '1d': df_1d,
                    '4h': self.load_data(symbol, '4h'),
                    '1h': self.load_data(symbol, '1h')
                }
                
                anti_profiles = []
                for _, row in anti_days.iterrows():
                    date = row['datetime']
                    snapshot = self.extract_dna_window(df_dict, date)
                    if snapshot:
                        anti_profiles.append({
                            "observation_date": date.isoformat(),
                            "dna": snapshot
                        })
                
                if anti_profiles:
                    anti_manifest[symbol] = anti_profiles
            except Exception:
                continue
                
        with open(self.profile_dir / "coin_antiDNA_profile.json", "w") as f:
            json.dump(anti_manifest, f, indent=4)
        print(f"Anti-DNA extraction complete. Profiles saved for {len(anti_manifest)} coins.")

if __name__ == "__main__":
    extractor = AntiDNAExtractor()
    extractor.run() # Full universe
