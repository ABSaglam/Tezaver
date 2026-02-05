import pandas as pd
import numpy as np
import json
import sys
import argparse
from pathlib import Path
import traceback

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "coin_cells/AVAXUSDT/src"))
import utils_io
import avax_learn_core
import core_indicators_v3
import v17_schema

BASE_DIR = Path("/Users/alisaglam/TezaverMac")
COIN_CELLS = BASE_DIR / "coin_cells"
OUT_ROOT_NAME = "kader_v3_fixed"

TRAIN_START = pd.Timestamp("2023-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2025-12-31", tz="UTC")

class CoinFactory:
    def __init__(self, symbol):
        self.symbol = symbol
        self.base_path = COIN_CELLS / symbol
        self.data_path = self.base_path / "data"
        self.out_path = self.base_path / "output" / OUT_ROOT_NAME / "runs/run_001"
        self.rules_path = self.out_path / "rules"
        self.reports_path = self.out_path / "reports"
        
        self.rules_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)
        
    def check_data(self):
        # Check files
        required = [
            f"{self.symbol}_1d.csv", 
            f"{self.symbol}_4h.csv", 
            f"{self.symbol}_1h.csv"
        ]
        # Parquet fallback handled by utils_io usually but let's check basic existence
        # Check if dir exists
        if not self.data_path.exists():
            return False, "NO_DATA_DIR"
            
        # We need at least 1D and 4H for V3
        has_1d = (self.data_path / f"history_1d.parquet").exists() or (self.data_path / f"{self.symbol}_1d.csv").exists()
        has_4h = (self.data_path / f"history_4h.parquet").exists() or (self.data_path / f"{self.symbol}_4h.csv").exists()
        
        if not (has_1d and has_4h):
            return False, "MISSING_CORE_DATA"
            
        return True, "OK"

    def load_data_bundle(self):
        # Use utils_io to robustly load
        return utils_io.get_data_bundle(self.symbol)

    def learn_dna(self, df_1d):
        # Calculate Features
        df = avax_learn_core.calculate_technical_features(df_1d, None, None, None)
        df = core_indicators_v3.calculate_extended_indicators(df)
        df = avax_learn_core.generate_labels(df)
        
        # Split Train
        mask = (df['datetime'] >= TRAIN_START) & (df['datetime'] <= TRAIN_END)
        df_train = df[mask].copy()
        
        if len(df_train) < 100:
            raise ValueError("INSUFFICIENT_HISTORY")
            
        df_yes = df_train[df_train['Hit_10'] == 'YES']
        if len(df_yes) < 5:
            raise ValueError(f"INSUFFICIENT_HITS (Found {len(df_yes)} matches in 2 years)")
            
        # 1. FAIL RULES
        fail_rules = {}
        df_no = df_train[df_train['Hit_10'] == 'NO']
        cols = ['Wick_Ratio', 'Dist_EMA', 'ATR_Norm', 'Energy_Gap', 'Anti_Penalty', 'Drift_Factor']
        for col in cols:
            p02 = df_yes[col].quantile(0.02)
            p98 = df_yes[col].quantile(0.98)
            # Add simple guards
            fail_rules[col] = {"min_hard": float(p02), "max_hard": float(p98)}
            
        # Suppression
        supp = df_train[df_train['STATE_RIBBON_SUPPRESSION_UP'] == True]
        if len(supp) > 0:
             fail_rate = len(supp[supp['Hit_10']=='NO']) / len(supp)
             fail_rules['suppression_veto'] = {"active": (fail_rate > 0.85)} # Adaptive threshold
        
        # 2. SUCCESS CORRIDOR (P15-P85 SQUEEZE)
        success_corridor = {}
        for col in ['ATR_Norm', 'Energy_Gap', 'Wick_Ratio', 'Dist_EMA']:
            p15 = df_yes[col].quantile(0.15)
            p85 = df_yes[col].quantile(0.85)
            success_corridor[col] = {"min": float(p15), "max": float(p85)}
            
        # ADX Floor (Fixed V3 Standard)
        success_corridor['ADX'] = {"min": 35.0, "max": 100.0}
        
        # 3. CANCEL RULES (Standard Fixed)
        # We can implement learning later, but user mandate is "AVAX Template" -> 0.28 Wick
        cancel_rules = {
            "wick_ratio_4h": {"threshold": 0.28},
            "4h_ribbon_trap": {"check": True, "condition": "RIBBON_INSIDE and RSI < RSI_EMA"}
        }
        
        # 4. TRIGGER MAP (Standard)
        trig_map = {"priority": "STANDARD"}
        
        # Save
        utils_io.save_json_rule(fail_rules, self.rules_path / f"{self.symbol}_fail_rules.json")
        utils_io.save_json_rule(success_corridor, self.rules_path / f"{self.symbol}_success_corridor.json")
        utils_io.save_json_rule(cancel_rules, self.rules_path / f"{self.symbol}_intraday_cancel_rules.json")
        utils_io.save_json_rule(trig_map, self.rules_path / f"{self.symbol}_trigger_map.json")
        
        return fail_rules, success_corridor, cancel_rules, trig_map, df

    def simulate(self, df_1d, df_4h, df_1h, rules):
        fail, succ, cancel, trig = rules
        
        # Pre-calc Intraday Indicators
        df_4h = core_indicators_v3.calculate_extended_indicators(df_4h)
        df_1h = core_indicators_v3.calculate_extended_indicators(df_1h)
        # Note: df_1d already processed in learn step
        
        # Test Split
        df_test = df_1d.iloc[-100:].copy()
        
        results = []
        logs = []
        
        for idx, row in df_test.iterrows():
            # Intraday Check
            target_date = row['datetime'].date()
            mask_4h = df_4h['datetime'].dt.date == target_date
            df_4h_day = df_4h[mask_4h]
            mask_1h = df_1h['datetime'].dt.date == target_date
            df_1h_day = df_1h[mask_1h]
            
            # Logic (Inline from fixed simulator to ensure self-containment)
            # DAILY GATES
            reasons = []
            vetoed = False
            
            # Fail Rules check
            for col, limits in fail.items():
                if col=="suppression_veto": continue
                val = row.get(col)
                if val is not None:
                    if val < limits.get('min_hard', -999): vetoed=True; reasons.append(f"{col}_LOW")
                    if val > limits.get('max_hard', 999): vetoed=True; reasons.append(f"{col}_HIGH")
            
            supp = fail.get('suppression_veto', {})
            if supp.get('active') and row.get('STATE_RIBBON_SUPPRESSION_UP'): 
                vetoed=True; reasons.append("SUPPRESSION")
                
            # Corridor
            in_corridor = True
            for col, bands in succ.items():
                val = row.get(col)
                if val is not None:
                    if val < bands['min'] or val > bands['max']:
                        in_corridor=False; reasons.append(f"{col}_OUT")
            
            daily_pass = (not vetoed) and in_corridor
            
            # HARD CANCEL
            is_canceled = False
            cancel_why = "NONE"
            
            if daily_pass: # Only check cancel if daily passed (optimization)
                # Wick 4H
                if len(df_4h_day) > 0:
                    body_top = df_4h_day[['open', 'close']].max(axis=1)
                    mean_wick = ((df_4h_day['high'] - body_top) / (df_4h_day['high'] - df_4h_day['low']).replace(0, np.nan)).fillna(0).mean()
                    if mean_wick > cancel.get('wick_ratio_4h',{}).get('threshold', 0.28):
                        is_canceled = True
                        cancel_why = f"WICK_4H ({mean_wick:.2f})"
                        
                # Ribbon Trap
                # Simple check: 50% bars suppression
                if not is_canceled and len(df_4h_day) > 0:
                    cnt = len(df_4h_day[df_4h_day['STATE_RIBBON_SUPPRESSION_UP'] == True])
                    if cnt/len(df_4h_day) >= 0.5:
                        is_canceled = True
                        cancel_why = "RIBBON_TRAP_4H"
            
            # Final Decision
            decision = "NO"
            verdict = "RED"
            tier = "SILVER"
            if daily_pass:
                if is_canceled:
                    decision = "NO" # Cancelled
                    verdict  = "RED"
                else:
                    # Trigger Check (Mock)
                    if row.get('Micro_Trig') == False and not (row.get('STATE_RSI_LOCK_UP') or row.get('STATE_RIBBON_BREAK_UP')):
                        decision = "WATCH" # No trigger
                        verdict = "RED"
                        reasons.append("NO_TRIGGER")
                    else:
                        decision = "NET_ADAY"
                        verdict = "ONY"
                        tier = "DIAMOND"
            else:
                 decision = "WATCH" if in_corridor else "NO"
                 # Simplify:
                 decision = "NO"
                 
            # Log
            logs.append({
                "Date": row['datetime'].isoformat(),
                "DailyGatePass": daily_pass,
                "IntradayCancelApplied": is_canceled,
                "CancelReason": cancel_why,
                "FinalDecision": decision,
                "Hit_10": row['Hit_10']
            })
            
            # V17 Row
            res_row = {}
            for col in v17_schema.V17_COLUMNS:
                if col == "Date": res_row[col] = row['datetime'].isoformat()
                elif col == "Symbol": res_row[col] = self.symbol
                elif col == "Tier": res_row[col] = tier
                elif col == "Audit_Verdict": res_row[col] = verdict
                elif col in row: res_row[col] = row[col]
                else: res_row[col] = 0.0
            res_row['Decision'] = decision
            res_row['Reason'] = " ".join(reasons) if not is_canceled else cancel_why
            results.append(res_row)
            
        # Save
        df_res = pd.DataFrame(results)
        df_log = pd.DataFrame(logs)
        
        df_res[v17_schema.V17_COLUMNS].to_csv(self.reports_path / f"{self.symbol}_V17_TEST_DAILY.csv", index=False)
        df_net = df_res[df_res['Decision']=='NET_ADAY']
        df_net[v17_schema.V17_COLUMNS].to_csv(self.reports_path / f"{self.symbol}_NET_ADAY_REPORT.csv", index=False)
        df_log.to_csv(self.reports_path / f"{self.symbol}_SIMULATION_STAGE_LOG.csv", index=False)
        
        return df_res, df_log

    def generate_autopsy(self, df_res, df_log):
        net_adays = len(df_res[df_res['Decision']=='NET_ADAY'])
        hits = len(df_res[(df_res['Decision']=='NET_ADAY') & (df_res['Hit_10']=='YES')])
        wr = hits/net_adays*100 if net_adays > 0 else 0
        
        # Cancel Stats
        cancels = df_log[df_log['IntradayCancelApplied']==True]
        cancel_reasons = cancels['CancelReason'].value_counts().to_dict()
        
        md = f"# 🧬 {self.symbol} AUTOPSY REPORT (V3 FIXED)\n\n"
        md += f"- **NET ADAYS:** {net_adays}\n"
        md += f"- **HIT RATE:** {wr:.2f}%\n"
        md += f"- **CANCELS:** {len(cancels)} days cancelled hard.\n"
        md += f"  - Breakdown: {cancel_reasons}\n"
        
        with open(self.reports_path / f"{self.symbol}_AUTOPSY_PACK.md", "w") as f:
            f.write(md)

    def run(self):
        print(f"::: PROCESSING {self.symbol} :::")
        ok, msg = self.check_data()
        if not ok:
            print(f"SKIP {self.symbol}: {msg}")
            return "SKIP", msg
            
        try:
            bundle = self.load_data_bundle()
            fail, succ, cancel, trig, df_learned = self.learn_dna(bundle['1d'])
            df_res, df_log = self.simulate(df_learned, bundle['4h'], bundle['1h'], (fail, succ, cancel, trig))
            self.generate_autopsy(df_res, df_log)
            print(f"SUCCESS {self.symbol}")
            return "SUCCESS", "OK"
        except Exception as e:
            traceback.print_exc()
            print(f"FAIL {self.symbol}: {e}")
            return "FAIL", str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="coins_universe.txt")
    parser.add_argument("--max_coins", type=int, default=999)
    args = parser.parse_args()
    
    with open(args.universe) as f:
        coins = [line.strip() for line in f if line.strip()]
        
    log = []
    processed = 0
    
    for coin in coins:
        if processed >= args.max_coins: break
        
        factory = CoinFactory(coin)
        status, reason = factory.run()
        log.append({"Symbol": coin, "Status": status, "Reason": reason})
        if status == "SUCCESS":
            processed += 1
            
    pd.DataFrame(log).to_csv("FACTORY_RUN_LOG.csv", index=False)
    
if __name__ == "__main__":
    main()
