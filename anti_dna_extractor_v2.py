import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from tqdm import tqdm
import random

class AntiDNAExtractorV2:
    def __init__(self, base_dir="coin_cells", profile_dir="DNA_Profiles"):
        self.base_dir = Path(base_dir)
        self.profile_dir = Path(profile_dir)
        self.start_date = pd.Timestamp("2023-01-01", tz="UTC")
        self.end_date = pd.Timestamp("2025-12-31", tz="UTC")
        self.symbols = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    def load_data(self, symbol, timeframe):
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists(): return None
        df = pd.read_parquet(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df[(df['datetime'] >= self.start_date) & (df['datetime'] <= self.end_date)]
        return df

    def find_anti_days_v2(self, df_1d, exp_dates):
        """Enhanced Anti-DNA identification: Failed breakouts & Exhaustion."""
        if df_1d is None or len(df_1d) < 30: return []
        
        df = df_1d.copy()
        df['atr'] = (df['high'] - df['low']).rolling(14).mean()
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['next_high_ratio'] = (df['high'].shift(-1) / df['close']) - 1
        
        # 1. Failed Compression Breakout
        # ATR was low, then jumped, but next day failed.
        failed_breakout = df[
            (df['atr'] < df['atr'].shift(1) * 1.5) & # was tightening
            (df['volume'] > df['vol_ma'] * 1.5) & # vol spike
            (df['next_high_ratio'] < 0.05) & # failed expansion
            (~df['datetime'].isin(exp_dates))
        ]
        
        # 2. Trend Exhaustion (Volume spike after rally)
        # Price moved up significantly relative to EMA but volume spiked + reversal wick
        ema20 = df['close'].ewm(span=20).mean()
        exhaustion = df[
            (df['close'] > ema20 * 1.1) & # extended
            (df['volume'] > df['vol_ma'] * 2) & # volume climax
            (df['close'] < df['high']) & # wick on top
            (df['next_high_ratio'] < 0.02)
        ]
        
        # 3. Simple Noise (Similar to old anti-DNA)
        noise = df[
            (df['atr'] < df['atr'].median()) &
            (df['next_high_ratio'] < 0.03) &
            (~df['datetime'].isin(exp_dates))
        ]
        
        # Combine all types
        candidates = pd.concat([failed_breakout, exhaustion, noise]).drop_duplicates(subset=['datetime'])
        
        if len(candidates) == 0: return []
        
        # Sample to match DNA density
        num_to_sample = min(len(candidates), max(10, len(exp_dates)))
        return candidates.sample(n=num_to_sample)

    def extract_dna_window(self, df_dict, target_date):
        dna_snapshot = {}
        cutoff = target_date
        
        for tf, df in df_dict.items():
            if df is None: continue
            
            pre_window = df[df['datetime'] < cutoff].tail(50 * (24 if tf == '1h' else 1))
            if len(pre_window) < 30: continue
            
            atr_series = (pre_window['high'] - pre_window['low']).rolling(14).mean()
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

    def run(self, limit=None):
        # Load existing ROLLING DNA profiles
        with open(self.profile_dir / "rolling_DNA_profile.json", "r") as f:
            dna_manifest = json.load(f)
            
        anti_manifest = {}
        target_symbols = list(dna_manifest.keys())[:limit] if limit else list(dna_manifest.keys())
        
        print(f"Extracting ENHANCED Anti-DNA profiles for {len(target_symbols)} symbols...")
        for symbol in tqdm(target_symbols):
            try:
                df_1d = self.load_data(symbol, '1d')
                if df_1d is None: continue
                
                exp_dates = [pd.to_datetime(d['expansion_date']) for d in dna_manifest[symbol]]
                anti_days = self.find_anti_days_v2(df_1d, exp_dates)
                
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
    extractor = AntiDNAExtractorV2()
    extractor.run()
