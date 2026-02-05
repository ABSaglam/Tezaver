import pandas as pd
import numpy as np
import json
import sys
import argparse
from pathlib import Path
import traceback
import hashlib

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir / "coin_cells/AVAXUSDT/src"))
import utils_io
import avax_learn_core
import core_indicators_v3
import v17_schema

BASE_DIR = Path("/Users/alisaglam/TezaverMac")
COIN_CELLS = BASE_DIR / "coin_cells"
OUT_ROOT_NAME = "kader_v3_fixed"
FAILED_LOG = BASE_DIR / "FAILED_COINS.csv"

TRAIN_START = pd.Timestamp("2023-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2025-12-31", tz="UTC")

class OneByOneFactory:
    def __init__(self, symbol):
        self.symbol = symbol
        self.base_path = COIN_CELLS / symbol
        self.data_path = self.base_path / "data"
        self.out_path = self.base_path / "output" / OUT_ROOT_NAME / "runs/run_001"
        self.rules_path = self.out_path / "rules"
        self.reports_path = self.out_path / "reports"
        self.complete_file = self.base_path / "output" / OUT_ROOT_NAME / "COMPLETE.ok"
        
        self.rules_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)
        
    def is_complete(self):
        return self.complete_file.exists()

    def check_data(self):
        if not self.data_path.exists(): return False, "NO_DATA_DIR"
        has_1d = (self.data_path / f"history_1d.parquet").exists() or (self.data_path / f"{self.symbol}_1d.csv").exists()
        has_4h = (self.data_path / f"history_4h.parquet").exists() or (self.data_path / f"{self.symbol}_4h.csv").exists()
        if not (has_1d and has_4h): return False, "MISSING_CORE_DATA"
        return True, "OK"

    def load_data_bundle(self):
        return utils_io.get_data_bundle(self.symbol)

    def learn_dna(self, df_1d):
        # Features
        df = avax_learn_core.calculate_technical_features(df_1d, None, None, None)
        df = core_indicators_v3.calculate_extended_indicators(df)
        df = avax_learn_core.generate_labels(df)
        
        # Train Split
        mask = (df['datetime'] >= TRAIN_START) & (df['datetime'] <= TRAIN_END)
        df_train = df[mask].copy()
        
        if len(df_train) < 100: raise ValueError("INSUFFICIENT_HISTORY")
        df_yes = df_train[df_train['Hit_10'] == 'YES']
        if len(df_yes) < 5: raise ValueError(f"INSUFFICIENT_HITS ({len(df_yes)})")

        # 1. FAIL RULES
        fail_rules = {}
        for col in ['Wick_Ratio', 'Dist_EMA', 'ATR_Norm', 'Energy_Gap']:
            p02, p98 = df_yes[col].quantile(0.02), df_yes[col].quantile(0.98)
            fail_rules[col] = {"min_hard": float(p02), "max_hard": float(p98)}
        
        supp = df_train[df_train['STATE_RIBBON_SUPPRESSION_UP'] == True]
        if len(supp) > 0:
             fail_rate = len(supp[supp['Hit_10']=='NO']) / len(supp)
             fail_rules['suppression_veto'] = {"active": (fail_rate > 0.85)}

        # 2. SUCCESS CORRIDOR
        success_corridor = {}
        for col in ['ATR_Norm', 'Energy_Gap', 'Wick_Ratio', 'Dist_EMA']:
            p15, p85 = df_yes[col].quantile(0.15), df_yes[col].quantile(0.85)
            success_corridor[col] = {"min": float(p15), "max": float(p85)}
        success_corridor['ADX'] = {"min": 35.0, "max": 100.0}

        # 3. CANCEL & TRIGGER
        cancel_rules = {
            "wick_ratio_4h": {"threshold": 0.28},
            "4h_ribbon_trap": {"check": True, "condition": "RIBBON_INSIDE and RSI < RSI_EMA"}
        }
        trig_map = {"priority": "STANDARD"}
        
        # Save
        utils_io.save_json_rule(fail_rules, self.rules_path / f"{self.symbol}_fail_rules.json")
        utils_io.save_json_rule(success_corridor, self.rules_path / f"{self.symbol}_success_corridor.json")
        utils_io.save_json_rule(cancel_rules, self.rules_path / f"{self.symbol}_intraday_cancel_rules.json")
        utils_io.save_json_rule(trig_map, self.rules_path / f"{self.symbol}_trigger_map.json")
        
        return fail_rules, success_corridor, cancel_rules, trig_map, df

    def get_forward_outcomes(self, df_1d):
        # Pre-calc 24h/48h max excursion for ALL days for False Negative check
        # Returns dict {date: {max24, max48}}
        outcomes = {}
        closes = df_1d['close'].values
        highs = df_1d['high'].values
        dates = df_1d['datetime'].dt.date.values
        
        for i in range(len(df_1d)-2):
            dt = dates[i]
            c0 = closes[i]
            h1 = highs[i+1]
            h2 = highs[i+2]
            
            max_24 = (h1/c0 - 1)*100
            max_48 = (max(h1, h2)/c0 - 1)*100
            
            outcomes[dt] = {"max_24": max_24, "max_48": max_48}
            
        return outcomes

    def simulate(self, df_1d, df_4h, df_1h, rules):
        fail, succ, cancel, trig = rules
        
        # Intraday Indic
        df_4h = core_indicators_v3.calculate_extended_indicators(df_4h)
        df_1h = core_indicators_v3.calculate_extended_indicators(df_1h)
        
        # Outcomes Lookahead
        outcomes = self.get_forward_outcomes(df_1d)
        
        df_test = df_1d.iloc[-100:].copy()
        results, logs = [], []
        
        for idx, row in df_test.iterrows():
            target_date = row['datetime'].date()
            
            # Intraday Data
            df_4h_day = df_4h[df_4h['datetime'].dt.date == target_date]
            
            # 1. DAILY
            reasons = []
            vetoed = False
            for col, limits in fail.items():
                if col=="suppression_veto": continue
                val = row.get(col)
                if val:
                    if val < limits.get('min_hard', -999): vetoed=True; reasons.append(f"{col}_LOW")
                    if val > limits.get('max_hard', 999): vetoed=True; reasons.append(f"{col}_HIGH")
            
            if fail.get('suppression_veto', {}).get('active') and row.get('STATE_RIBBON_SUPPRESSION_UP'):
                vetoed=True; reasons.append("SUPPRESSION")
                
            in_corridor = True
            for col, bands in succ.items():
                val = row.get(col)
                if val and (val < bands['min'] or val > bands['max']):
                    in_corridor=False; reasons.append(f"{col}_OUT")
            
            daily_pass = (not vetoed) and in_corridor
            
            # 2. HARD CANCEL
            is_canceled, cancel_why = False, "NONE"
            if daily_pass:
                # Wick
                if len(df_4h_day) > 0:
                    body_top = df_4h_day[['open', 'close']].max(axis=1)
                    hl = (df_4h_day['high'] - df_4h_day['low']).replace(0, np.nan)
                    mean_wick = ((df_4h_day['high'] - body_top) / hl).fillna(0).mean()
                    if mean_wick > cancel.get('wick_ratio_4h',{}).get('threshold', 0.28):
                        is_canceled = True; cancel_why = f"WICK_4H ({mean_wick:.2f})"
                
                # Ribbon Trap
                if not is_canceled and len(df_4h_day) > 0:
                    cnt = len(df_4h_day[df_4h_day['STATE_RIBBON_SUPPRESSION_UP'] == True])
                    if cnt/len(df_4h_day) >= 0.5:
                        is_canceled = True; cancel_why = "RIBBON_TRAP"

            # Verdict
            decision, verdict, tier = "NO", "RED", "SILVER"
            if daily_pass:
                if is_canceled:
                    decision, verdict = "NO", "RED"
                else:
                    if row.get('Micro_Trig') == False and not (row.get('STATE_RSI_LOCK_UP') or row.get('STATE_RIBBON_BREAK_UP')):
                        decision, verdict = "WATCH", "RED"; reasons.append("NO_TRIGGER")
                    else:
                        decision, verdict, tier = "NET_ADAY", "ONY", "DIAMOND"
            else:
                 decision = "WATCH" if in_corridor else "NO"
                 # Simplify NO for non-pass
                 if not in_corridor: decision = "NO"
                 
            # Outcome (Counterfactual)
            fut = outcomes.get(target_date, {"max_24": 0.0, "max_48": 0.0})
            
            logs.append({
                "Date": row['datetime'].isoformat(),
                "DailyGate": daily_pass,
                "Cancel": is_canceled,
                "CancelReason": cancel_why,
                "FinalDecision": decision,
                "Max24": fut['max_24'],
                "Max48": fut['max_48']
            })
            
            res_row = {col: row.get(col, 0.0) for col in v17_schema.V17_COLUMNS}
            res_row['Date'] = row['datetime'].isoformat()
            res_row['Symbol'] = self.symbol
            res_row['Tier'] = tier
            res_row['Audit_Verdict'] = verdict
            res_row['Decision'] = decision
            res_row['Reason'] = " ".join(reasons) if not is_canceled else cancel_why
            results.append(res_row)

        df_res = pd.DataFrame(results)
        df_log = pd.DataFrame(logs)
        
        df_res[v17_schema.V17_COLUMNS].to_csv(self.reports_path / f"{self.symbol}_V17_TEST_DAILY.csv", index=False)
        df_res[df_res['Decision']=='NET_ADAY'][v17_schema.V17_COLUMNS].to_csv(self.reports_path / f"{self.symbol}_NET_ADAY_REPORT.csv", index=False)
        df_log.to_csv(self.reports_path / f"{self.symbol}_SIMULATION_STAGE_LOG.csv", index=False)
        
        return df_res, df_log

    def generate_pack(self, df_log):
        # Stats
        net = df_log[df_log['FinalDecision']=='NET_ADAY']
        net_cnt = len(net)
        
        # Hits (>=10%)
        hits24 = len(net[net['Max24'] >= 10.0])
        hits48 = len(net[net['Max48'] >= 10.0])
        
        hr24 = hits24/net_cnt*100 if net_cnt>0 else 0
        hr48 = hits48/net_cnt*100 if net_cnt>0 else 0
        
        # False Pos (Net Aday but Fail)
        fp_cnt = net_cnt - hits48 # Using 48h as ultimate truth
        
        # False Neg (NO/WATCH but Hit 10%)
        ignored = df_log[df_log['FinalDecision']!='NET_ADAY']
        fn24 = len(ignored[ignored['Max24'] >= 10.0])
        fn48 = len(ignored[ignored['Max48'] >= 10.0])
        
        cancels = df_log[df_log['Cancel']==True]
        top_cancel = cancels['CancelReason'].mode()[0] if not cancels.empty else "None"
        
        # Autopsy MD
        md = f"# 🧬 {self.symbol} AUTOPSY (V3 FIXED)\n\n"
        md += f"## 1. Performance\n"
        md += f"- **NET ADAYS:** {net_cnt}\n"
        md += f"- **Hit Rate (24h):** {hr24:.1f}% ({hits24}/{net_cnt})\n"
        md += f"- **Hit Rate (48h):** {hr48:.1f}% ({hits48}/{net_cnt})\n\n"
        
        md += f"## 2. Precision/Recall\n"
        md += f"- **False Positives:** {fp_cnt} (Signal -> No Pump)\n"
        md += f"- **False Negatives:** {fn48} (No Signal -> Pumped 10%+)\n\n"
        
        md += f"## 3. Mechanisms\n"
        md += f"- **Hard Cancels:** {len(cancels)}\n"
        md += f"- **Top Cancel Reason:** {top_cancel}\n"
        
        with open(self.reports_path / f"{self.symbol}_AUTOPSY_PACK.md", "w") as f:
            f.write(md)
            
        # Summary JSON
        summary = {
            "symbol": self.symbol,
            "run_id": "run_001",
            "net_aday_count": int(net_cnt),
            "hitrate_24h": float(hr24),
            "hitrate_48h": float(hr48),
            "false_pos": int(fp_cnt),
            "false_neg_24h": int(fn24),
            "false_neg_48h": int(fn48),
            "top_cancel_reason": str(top_cancel)
        }
        
        with open(self.base_path / f"output/{OUT_ROOT_NAME}/SUMMARY_ONE_COIN.json", "w") as f:
            json.dump(summary, f, indent=2)

    def mark_complete(self):
        with open(self.complete_file, "w") as f:
            f.write("OK")

    def run(self):
        print(f"::: PROCESSING {self.symbol} :::")
        ok, msg = self.check_data()
        if not ok: raise Exception(msg)
        
        bundle = self.load_data_bundle()
        # Unpack 5 args
        fail, succ, cancel, trig, df_learned = self.learn_dna(bundle['1d'])
        # Pass df_learned to simulate
        df_res, df_log = self.simulate(df_learned, bundle['4h'], bundle['1h'], (fail, succ, cancel, trig))
        self.generate_pack(df_log)
        self.mark_complete()
        print(f"SUCCESS {self.symbol}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="coins_first10.txt")
    args = parser.parse_args()
    
    with open(args.universe) as f:
        coins = [line.strip() for line in f if line.strip()]
        
    for coin in coins:
        factory = OneByOneFactory(coin)
        if factory.is_complete():
            continue
            
        # Found incomplete coin
        try:
            factory.run()
            sys.exit(0) # Success -> Exit
        except Exception as e:
            traceback.print_exc()
            with open(FAILED_LOG, "a") as f:
                f.write(f"{coin},{str(e)}\n")
            sys.exit(1) # Fail -> Exit

    print("ALL COINS COMPLETE.")
    sys.exit(0)

if __name__ == "__main__":
    main()
