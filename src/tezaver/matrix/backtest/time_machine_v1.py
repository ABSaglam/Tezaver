"""
Matrix Time Machine V1
======================

Backtest engine that mocks the Cloud Runtime environment and replays history.
"""
import time
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

from tezaver.matrix.core.cloud_runtime import pool_step
from tezaver.matrix.backtest.paper_exchange_v1 import PaperExchange

class MatrixTimeMachine:
    def __init__(self, symbol: str, timeframe: str, start_balance: float = 1000.0):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = PaperExchange(initial_balance=start_balance)
        self.history_path = Path(f"coin_cells/{symbol}/data/history_{timeframe}.parquet")
        self.results = []
        
    def load_data(self):
        if not self.history_path.exists():
            raise FileNotFoundError(f"No history found at {self.history_path}")
        self.df = pd.read_parquet(self.history_path)
        # Ensure sorting
        if "timestamp" in self.df.columns:
            self.df = self.df.sort_values("timestamp")
        
    def run(self, manifest: dict, start_ts: int = 0, end_ts: int = 0) -> Dict[str, Any]:
        """
        Run the simulation.
        
        Args:
            manifest: Bundle manifest dictionary
            start_ts: Start timestamp (ms)
            end_ts: End timestamp (ms)
            
        Returns:
            Dict containing equity curve, trades, and summary stats.
        """
        from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1
        from tezaver.matrix.backtest.signal_generator_v1 import SignalGenerator
        from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool
        from tezaver.matrix.pool_court.pool_court_models_v1 import PoolJuryScorecardV1
        
        try:
            m_obj = ApprovedRallyBundleManifestV1.from_dict(manifest)
        except Exception as e:
            return {"error": f"Invalid Bundle Manifest: {e}"}

        print(f"Starting Time Machine for {self.symbol} ({self.timeframe})...")
        
        # 1. Load Data
        self.load_data()
        
        # Filter Data
        df = self.df
        if start_ts > 0:
            df = df[df['timestamp'] >= start_ts]
        if end_ts > 0:
            df = df[df['timestamp'] <= end_ts]
            
        if df.empty:
            return {"error": "No data in range"}
            
        # 2. Generate Signals
        print("Generating Signals...")
        signals_list = SignalGenerator.generate_intents(df, m_obj)
        # Map signals by timestamp for O(1) lookup
        signals_map = {s["timestamp"]: s["intent"] for s in signals_list}
        print(f"Generated {len(signals_list)} signals.")
        
        # 3. Simulation Loop
        # We iterate through the dataframe
        # Optimization: iterrows is slow. 
        # But we need sequential state (Exchange positions).
        # We can just iterate row dicts.
        
        records = df.to_dict('records')
        
        decision_log = []
        
        for row in records:
            ts = int(row['timestamp'])
            
            # A. Update Exchange State (TP/SL checks)
            # Pass Candle: Open, High, Low, Close
            candle = {
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"]
            }
            
            # We assume "Current Time" is the CLOSE time of this bar.
            # So checks happen for this bar's price action.
            self.exchange.execute_logic(ts, self.symbol, candle, "NONE") # Just checks
            
            # B. Check for Signal
            intent = signals_map.get(ts)
            
            verdict_result = "NONE"
            decision_action = "NONE"
            
            if intent:
                # C. Run Court Logic (Judge)
                # Build Mock Scorecard
                # We assume if Intent exists, it passed Defender (mostly).
                # Defense logic (Cert etc) should be checked here if we want full realism.
                # SignalGen generally assumes "Trigger Met".
                
                # Mock Scorecard
                # We need to simulate Risk State (Blocked Reasons).
                # For basic backtest, assume Risk OK unless Exchange says "No Funds".
                
                # Check Exchange "Risk" (Funds)
                # Actually Judge handles "Global Risk".
                # Let's assume passed for now.
                
                scorecard = PoolJuryScorecardV1(
                    run_id=f"SIM_{ts}",
                    stage="BACKTEST",
                    engine_version="v1_sim",
                    data_fingerprint="sim",
                    config_signature="sim",
                    built_ts_iso=intent.created_ts_iso,
                    evidence_ok=True,
                    universe_cells=1,
                    intents_created=1, # We have one
                    selected_count=1, # Assume selected
                    allowed_count=0, # To be determined
                    blocked_count=0,
                    planned_orders=0, # To be determined
                    planned_total_notional=0.0,
                    restart_reconcile_verdict="OK",
                    kill_switch_triggered=False,
                    blocked_reasons_count={},
                    skipped_reasons_count={},
                    limits={},
                    key_notes=[]
                )
                
                # But Judge logic relies on 'blocked_count' or 'gates'.
                # The real 'judge_pool' is stateless regarding history, it decides based on scorecard.
                # If Scorecard is clean, Verdict is PASS.
                
                # We need to simulate "Is this intent valid?"
                # If we have intent, it's valid.
                scorecard.planned_orders = 1 # We claim we plan it
                
                # RUN JUDGE
                ctx = {}
                v_obj = judge_pool(scorecard, ctx, {})
                decision_action = v_obj.decision_action
                
                # D. Execute Decision
                if decision_action == "ALLOW":
                    # Pass the proposed notional from intent (manifest policy)
                    plan = intent.proposed_notional
                    self.exchange.execute_logic(ts, self.symbol, candle, "ALLOW", plan_notional=plan)
                
                decision_log.append({
                    "ts": ts,
                    "intent_id": intent.intent_id,
                    "decision": decision_action,
                    "verdict": v_obj.verdict
                })
            
            # E. Record Equity
            eq = self.exchange.get_equity({self.symbol: row["close"]})
            self.results.append({
                "ts": ts,
                "date": row.get("datetime", str(ts)),
                "balance": self.exchange.balance,
                "equity": eq,
                "price": row["close"]
            })
            
        return {
            "equity_curve": self.results,
            "trades": self.exchange.trades,
            "decisions": decision_log,
            "final_balance": self.exchange.balance,
            "final_equity": self.results[-1]["equity"] if self.results else 0
        }

