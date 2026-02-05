import pandas as pd
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm
from matching_engine_v2 import DNAMatchingEngineV2

class TriggerDetector:
    """Detects 'Ignition' micro-triggers on lower timeframes."""
    @staticmethod
    def check_trigger(df_15m, df_1h):
        if df_15m is None or len(df_15m) < 25: return False, "No data"
        
        # 1. Micro Volatility Expansion
        # Is the recent 15m range expanding?
        last_2_ranges = (df_15m['high'] - df_15m['low']).tail(2).mean()
        baseline_range = (df_15m['high'] - df_15m['low']).tail(20).median()
        is_vol_expanding = last_2_ranges > (baseline_range * 1.4)
        
        # 2. Volume Micro-Spike
        # Recent 15m volume vs baseline
        last_vol = df_15m['volume'].iloc[-1]
        baseline_vol = df_15m['volume'].tail(20).median()
        is_vol_spike = last_vol > (baseline_vol * 2.5)
        
        # 3. Structure Hold (Micro)
        # Price holding above 15m SMA20
        sma20 = df_15m['close'].rolling(20).mean().iloc[-1]
        is_holding = df_15m['close'].iloc[-1] > sma20
        
        # 4. Momentum Rhythm (RSI 15m)
        # Simplified RSI implementation
        delta = df_15m['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        is_mom_good = rsi.iloc[-1] > 60
        
        # Trigger requires Volume Spike AND (Vol Expansion OR Mom Growth) AND Holding Structure
        if is_vol_spike and (is_vol_expanding or is_mom_good) and is_holding:
            return True, "Volume Spike + Momentum/Vol expansion"
        return False, "Not triggered"

class ScannerV2TierS:
    def __init__(self, base_dir="coin_cells", report_dir="Reports"):
        self.base_dir = Path(base_dir)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(exist_ok=True)
        self.matching_engine = DNAMatchingEngineV2()
        self.symbols = list(self.matching_engine.dna_profiles.keys())

    def load_full_data(self, symbol, timeframe):
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists(): return None
        df = pd.read_parquet(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df

    def get_habitat_snapshot(self, df_dict, current_date):
        snapshot = {}
        for tf in ['1d', '4h', '1h']:
            df = df_dict.get(tf)
            if df is None: continue
            pre_window = df[df['datetime'] < current_date].tail(50 * (24 if tf == '1h' else 1))
            if len(pre_window) < 30: continue
            
            atr_series = (pre_window['high'] - pre_window['low']).rolling(14).mean()
            norm_atr = float(atr_series.iloc[-1] / pre_window['close'].iloc[-1])
            ranges = (pre_window['high'] - pre_window['low']).tail(5)
            slope = float(np.polyfit(range(len(ranges)), ranges, 1)[0] / (ranges.mean() + 1e-9))
            ema20 = pre_window['close'].ewm(span=20).mean()
            ema_dist = float(abs(pre_window['close'].iloc[-1] - ema20.iloc[-1]) / (ema20.iloc[-1] + 1e-9))
            vol_contraction = float(pre_window['volume'].tail(3).mean() / (pre_window['volume'].mean() + 1e-9))
            volt_ratio = float(atr_series.iloc[-1] / (atr_series.iloc[-14:-1].mean() + 1e-9))
            wicks = (pre_window['high'] - pre_window[['open','close']].max(axis=1)).mean()
            wick_ratio = float(wicks / (pre_window['high'] - pre_window['low']).mean())
            
            snapshot[tf] = {
                "norm_atr": norm_atr, "range_slope": slope, "ema_dist": ema_dist,
                "vol_contraction": vol_contraction, "volt_ratio": volt_ratio,
                "wick_ratio": wick_ratio, "price_std": float(pre_window['close'].std() / (pre_window['close'].mean() + 1e-9))
            }
        return snapshot

    def run_simulation(self, habitat_threshold=0.55):
        start_jan = pd.Timestamp("2026-01-01", tz="UTC")
        end_jan = pd.Timestamp("2026-01-31", tz="UTC")
        all_dates = pd.date_range(start_jan, end_jan, freq='D', tz='UTC')
        
        upgraded_report = []
        
        print("Loading data map...")
        symbol_data = {}
        for symbol in tqdm(self.symbols):
            symbol_data[symbol] = {
                '1d': self.load_full_data(symbol, '1d'),
                '4h': self.load_full_data(symbol, '4h'),
                '1h': self.load_full_data(symbol, '1h'),
                '15m': self.load_full_data(symbol, '15m')
            }

        print("Running Upgraded TIER-S Simulation (Jan 2026)...")
        for current_date in tqdm(all_dates):
            for symbol, df_dict in symbol_data.items():
                if not df_dict['1d'] is not None: continue
                
                # 1. Habitat Check
                habitat_snap = self.get_habitat_snapshot(df_dict, current_date)
                if not habitat_snap: continue
                
                habitat_res = self.matching_engine.get_habitat_score(symbol, habitat_snap)
                if not habitat_res or habitat_res['habitat_score'] < habitat_threshold: continue
                
                # 2. Trigger Check (Micro context before scan time)
                # In sequential sim, 'current_date' 00:00:00 means we look at candles BEFORE this time.
                df_15m_part = df_dict['15m'][df_dict['15m']['datetime'] < current_date].tail(30)
                df_1h_part = df_dict['1h'][df_dict['1h']['datetime'] < current_date].tail(10)
                
                trigger_ok, trigger_msg = TriggerDetector.check_trigger(df_15m_part, df_1h_part)
                
                # TIER Classification
                score = habitat_res['habitat_score']
                if score > 0.65 and trigger_ok:
                    tier = "Tier S"
                elif score > 0.60:
                    tier = "Tier A"
                elif score > 0.55:
                    tier = "Tier B"
                else: continue
                
                # Outcome Tracking
                # Next day = candle starting at current_date
                next_day_cand = df_dict['1d'][df_dict['1d']['datetime'] == current_date]
                if next_day_cand.empty: continue
                
                prev_close_df = df_dict['1d'][df_dict['1d']['datetime'] < current_date].tail(1)
                if prev_close_df.empty: continue
                prev_close = prev_close_df['close'].iloc[0]
                
                max_move = (next_day_cand['high'].iloc[0] / prev_close) - 1
                close_move = (next_day_cand['close'].iloc[0] / prev_close) - 1
                hit_10 = "YES" if max_move >= 0.10 else "NO"
                
                upgraded_report.append({
                    "Date": current_date.date().isoformat(),
                    "Symbol": symbol,
                    "Tier": tier,
                    "Habitat Score": round(score, 3),
                    "Trigger?": "YES" if trigger_ok else "NO",
                    "Explanation": f"Habitat match with {trigger_msg}",
                    "Max %": round(max_move * 100, 2),
                    "Close %": round(close_move * 100, 2),
                    "Hit >=10%?": hit_10
                })

        # Reports
        df_res = pd.DataFrame(upgraded_report)
        df_res.to_csv(self.report_dir / "DNA_JAN2026_UPGRADED_DAILY.csv", index=False)
        
        # Tier S specific report
        df_s = df_res[df_res['Tier'] == "Tier S"]
        df_s.to_csv(self.report_dir / "DNA_TIER_S_REPORT.csv", index=False)
        
        # Performance Summary
        if not df_res.empty:
            p_v2 = {
                "Total Candidates": len(df_res),
                "Tier S Candidates": len(df_s),
                "Hits >=10%": sum(1 for _,r in df_res.iterrows() if r["Hit >=10%?"] == "YES"),
                "Hit Rate %": round((sum(1 for _,r in df_res.iterrows() if r["Hit >=10%?"] == "YES") / len(df_res)) * 100, 2),
                "Tier S Hit Rate %": round((sum(1 for _,r in df_s.iterrows() if r["Hit >=10%?"] == "YES") / len(df_s)) * 100, 2) if not df_s.empty else 0,
                "Avg Max %": round(df_res["Max %"].mean(), 2)
            }
            pd.DataFrame([p_v2]).to_csv(self.report_dir / "DNA_PERFORMANCE_V2.csv", index=False)
        
        print(f"\nSimulation Complete. Upgraded Candidates: {len(df_res)}")
        print(f"Tier S Count: {len(df_s)}")
        print(f"Reports saved in {self.report_dir}")

if __name__ == "__main__":
    scanner = ScannerV2TierS()
    scanner.run_simulation()
