import pandas as pd
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm
from dna_matching_engine import DNAMatchingEngine

class Scanner2026:
    def __init__(self, base_dir="coin_cells", report_dir="Reports"):
        self.base_dir = Path(base_dir)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(exist_ok=True)
        self.matching_engine = DNAMatchingEngine()
        self.start_date_2026 = pd.Timestamp("2026-01-01", tz="UTC")
        self.end_date_2026 = pd.Timestamp("2026-02-02", tz="UTC")
        self.symbols = list(self.matching_engine.dna_profiles.keys())

    def load_full_data(self, symbol, timeframe):
        file_path = self.base_dir / symbol / "data" / f"history_{timeframe}.parquet"
        if not file_path.exists(): return None
        df = pd.read_parquet(file_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df

    def get_snapshot(self, df_dict, current_date):
        """Extracts windows of data before the current date with ENHANCED metrics."""
        snapshot = {}
        cutoff = current_date
        
        for tf, df in df_dict.items():
            if df is None: continue
            
            # Ensure enough data for ATR(14) and 20-day EMA
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
            
            snapshot[tf] = {
                "norm_atr": norm_atr,
                "range_slope": slope,
                "ema_dist": ema_dist,
                "vol_contraction": vol_contraction,
                "volt_ratio": volt_ratio,
                "price_std": float(pre_window['close'].std() / (pre_window['close'].mean() + 1e-9))
            }
        return snapshot

    def run_simulation(self):
        # 1. Prepare January 2026 date range
        start_jan = pd.Timestamp("2026-01-01", tz="UTC")
        end_jan = pd.Timestamp("2026-01-31", tz="UTC")
        all_dates = pd.date_range(start_jan, end_jan, freq='D', tz='UTC')
        
        daily_report_data = [] # For DNA_JAN2026_DAILY_REPORT.csv
        
        # Load all data for target symbols once
        symbol_data = {}
        print("Loading data for all symbols...")
        for symbol in tqdm(self.symbols):
            try:
                symbol_data[symbol] = {
                    '1d': self.load_full_data(symbol, '1d'),
                    '4h': self.load_full_data(symbol, '4h'),
                    '1h': self.load_full_data(symbol, '1h')
                }
            except: continue

        print("Running January 2026 Sequential simulation...")
        for current_date in tqdm(all_dates):
            for symbol in self.symbols:
                df_dict = symbol_data.get(symbol)
                if not df_dict or df_dict['1d'] is None: continue
                
                # Snapshot current state
                curr_snapshot = self.get_snapshot(df_dict, current_date)
                if not curr_snapshot: continue
                
                # Match DNA (Threshold 0.4 for candidate status)
                match_result = self.matching_engine.get_match_score(symbol, curr_snapshot, threshold=0.4)
                
                if match_result and match_result['is_candidate']:
                    # Look at NEXT DAY result
                    # Next day candle is the one where datetime == current_date (daily candle starts at 00:00)
                    next_day = df_dict['1d'][df_dict['1d']['datetime'] == current_date]
                    if not next_day.empty:
                        row = next_day.iloc[0]
                        # prev_close is the close of the candle before current_date
                        prev_close_df = df_dict['1d'][df_dict['1d']['datetime'] < current_date].tail(1)
                        if prev_close_df.empty: continue
                        prev_close = prev_close_df['close'].iloc[0]
                        
                        max_move = (row['high'] / prev_close) - 1
                        close_move = (row['close'] / prev_close) - 1
                        
                        hit = "YES" if max_move >= 0.10 else "NO"
                        
                        tier = match_result['matched_tier']
                        
                        daily_report_data.append({
                            "Date": current_date.date().isoformat(),
                            "Symbol": symbol,
                            "Matched Tier": f"Tier {tier}",
                            "Explanation": f"Match with Tier {tier} historical DNA (Rel Score: {match_result['raw_match']:.2f})",
                            "Max %": round(max_move * 100, 2),
                            "Close %": round(close_move * 100, 2),
                            "Hit >=10%?": hit
                        })

        # --- GENERATE REPORTS ---
        
        # A. DAILY REPORT
        df_daily = pd.DataFrame(daily_report_data)
        df_daily.to_csv(self.report_dir / "DNA_JAN2026_DAILY_REPORT.csv", index=False)
        
        # B. PERFORMANCE SUMMARY
        if not df_daily.empty:
            summary = {
                "Total Candidates": len(df_daily),
                "True >=10% Expansions": sum(1 for _, r in df_daily.iterrows() if r["Hit >=10%?"] == "YES"),
                "False Positives": sum(1 for _, r in df_daily.iterrows() if r["Hit >=10%?"] == "NO"),
                "Average Max Excursion %": round(df_daily["Max %"].mean(), 2),
                "Hit Rate %": round((sum(1 for _, r in df_daily.iterrows() if r["Hit >=10%?"] == "YES") / len(df_daily)) * 100, 2)
            }
            pd.DataFrame([summary]).to_csv(self.report_dir / "DNA_JAN2026_PERFORMANCE_SUMMARY.csv", index=False)
            
            # Coin-wise success
            coin_success = df_daily.groupby("Symbol")["Hit >=10%?"].apply(lambda x: (x == "YES").sum()).reset_index()
            coin_success.columns = ["Symbol", "Total Hits"]
            coin_success.to_csv(self.report_dir / "DNA_JAN2026_COIN_SUCCESS.csv", index=False)
        
        print(f"\nSimulation complete. Results found: {len(df_daily)} candidates.")
        print(f"Reports saved in {self.report_dir}")

if __name__ == "__main__":
    scanner = Scanner2026()
    scanner.run_simulation()

if __name__ == "__main__":
    scanner = Scanner2026()
    scanner.run_simulation()
