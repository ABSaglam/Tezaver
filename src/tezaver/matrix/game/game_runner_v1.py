import pandas as pd
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Matrix Components
from tezaver.matrix.pool.pool_engine_v1 import PoolDefender
from tezaver.matrix.pool.pool_risk_engine_v1 import PoolProsecutor
from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool
from tezaver.matrix.pool_court.pool_jury_v1 import build_pool_scorecard, PoolJuryScorecardV1
from tezaver.matrix.pool.pool_models_v1 import PoolUniverseCellV1
from tezaver.matrix.backtest.signal_generator_v1 import SignalGenerator
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1

# Game Components
from tezaver.matrix.game.game_models_v1 import GameSummary, GameStep, GameTrade
from tezaver.matrix.game.game_execution_sim_v1 import GameExecutionSim
from tezaver.matrix.game.game_artifacts_v1 import GameArtifactsWriter
from tezaver.matrix.game.game_court_trace_v1 import GameCourtTraceNormalizer
from tezaver.matrix.game.game_metrics_v1 import GameMetricsV1
from tezaver.matrix.game.game_chart_marks_v1 import GameChartMarksV1

logger = logging.getLogger(__name__)

class GameRunnerV1:
    """
    GAME v1 Runner.
    Orchestrates replay, court simulation, and execution.
    """
    def __init__(self, runs_dir: str = "out/game_runs"):
        self.runs_dir = runs_dir
        
    def run(self, manifest: Dict[str, Any], history_df: pd.DataFrame, initial_capital: float = 100.0) -> Dict[str, Any]:
        run_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        writer = GameArtifactsWriter(self.runs_dir, run_id)
        
        # 1. Setup
        symbol = manifest.get("symbol", "UNKNOWN")
        tf = manifest.get("timeframe", "UNKNOWN")
        bundle_id = manifest.get("bundle_id", "UNKNOWN")
        
        # Write Manifest
        writer.write_manifest({
            "game_run_id": run_id,
            "bundle_id": bundle_id,
            "symbol": symbol,
            "timeframe": tf,
            "engine_version": "v1.0.0",
            "initial_capital": initial_capital,
            "config_signature": manifest.get("fingerprints", {}).get("config_signature"),
            "data_rows": len(history_df)
        })
        
        # 2. Components
        sim = GameExecutionSim(initial_capital=initial_capital)
        

        # 3. Pre-calculate Signals (Plan B optimization)
        # Convert dict to Manifest object if needed
        if isinstance(manifest, dict):
            try:
                m_obj = ApprovedRallyBundleManifestV1.from_dict(manifest)
            except:
                # Fallback empty if fail, though should not happen strictly
                m_obj = ApprovedRallyBundleManifestV1(
                    bundle_version="approved_rally_bundle_v1",
                    bundle_id=bundle_id, 
                    symbol=symbol, 
                    timeframe=tf,
                    event_id="dummy_event",
                    event_time_iso="2024-01-01T00:00:00Z",
                    approved_entry_bar_offset=0,
                    approved_entry_ts="2024-01-01T00:00:00Z",
                    qc_verdict="PASS",
                    qc_score=0, 
                    tier="test", 
                    scenario_id="test", 
                    narrative={},
                    trigger_spec_v1=manifest.get("trigger_spec_v1"),
                    policy_spec_v1=manifest.get("policy_spec_v1", {})
                )
        else:
            m_obj = manifest

        raw_signals = SignalGenerator.generate_intents(history_df, m_obj)
        
        # Convert to DataFrame for easy lookup
        if raw_signals:
            s_data = []
            for s in raw_signals:
                s_data.append({
                    "timestamp": int(s["timestamp"]),
                    "side": "BUY", # Assuming Long Only for now
                    "intent_obj": s["intent"]
                })
            intents_df = pd.DataFrame(s_data)
        else:
            intents_df = pd.DataFrame(columns=["timestamp", "side", "intent_obj"])
        
        steps: list[GameStep] = []
        pending_decision = None 
        
        # 4. Loop
        df = history_df.sort_values("open_time").reset_index(drop=True)
        
        for idx, row in df.iterrows():
            ts = int(row['open_time'])
            
            # --- T Open: Execution ---
            sim.on_bar_open(ts, row['open'], pending_decision, idx)
            
            # --- T Close: Court Logic ---
            has_signal = False
            intent_summary = "NONE"
            
            current_intents = intents_df[intents_df['timestamp'] == ts]
            
            # DEFEND
            if not current_intents.empty:
                intent_summary = f"{current_intents.iloc[0]['side']} @ {row['close']:.2f}"
                has_signal = True
                
            verdict_str = "SKIP"
            blocked_reasons = {}
            pending_decision = "NONE"
            
            if has_signal:
                # Mock Risk Check
                if sim.get_equity() < 50:
                    blocked_reasons["GLOBAL_EQUITY_LOW"] = 1
                
                # Verdict
                if not blocked_reasons:
                    verdict_str = "ALLOW"
                    pending_decision = "BUY"
                else:
                    verdict_str = "BLOCK"
            
            # Position Exit Logic (Simple SL/TP)
            if sim.position:
                entry = sim.position.entry_price
                curr = row['close']
                
                if curr > entry * 1.05:
                    pending_decision = "SELL"
                    intent_summary = "TP Exit"
                    verdict_str = "ALLOW"
                elif curr < entry * 0.95:
                    pending_decision = "SELL"
                    intent_summary = "SL Exit"
                    verdict_str = "ALLOW"
            
            # --- Store Step ---
            trace = GameCourtTraceNormalizer.normalize(
                verdict_obj=None, risk_report=None, scorecard=None, intents_report=None
            )
            
            if verdict_str == "BLOCK":
                 trace.verdict = "BLOCK"
                 for k in blocked_reasons:
                     trace.stage_reasons.append({"stage": "PROSECUTOR", "rule_code": "RISK", "detail": k})
            else:
                trace.verdict = verdict_str

            step = GameStep(
                ts=int(ts),
                bar_index=int(idx),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                intent_summary=intent_summary,
                verdict=verdict_str,
                court_trace=trace,
                equity_after=float(sim.get_equity()),
                position_state=str(sim.get_position_state()),
                trade_ref_id=None
            )
            steps.append(step)
            
        # 5. Finalize
        writer.write_steps(steps)
        writer.write_trades(sim.trades)
        
        # Summary
        trades_count = len(sim.trades)
        wins = len([t for t in sim.trades if t.pnl_net > 0])
        win_rate = (wins / trades_count) if trades_count > 0 else 0.0
        
        gross_profit = sum([t.pnl_gross for t in sim.trades if t.pnl_gross > 0])
        gross_loss = abs(sum([t.pnl_gross for t in sim.trades if t.pnl_gross < 0]))
        pf = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
        
        # Metrics
        max_dd = GameMetricsV1.calculate_max_drawdown(steps, initial_capital)
        
        # Count Verdicts
        v_counts = {"ALLOW": 0, "BLOCK": 0, "SKIP": 0}
        for s in steps:
            v = s.verdict
            if v in v_counts: v_counts[v] += 1
            else: v_counts[v] = 1
            
        summary = GameSummary(
            game_run_id=run_id,
            bundle_id=bundle_id,
            symbol=symbol,
            timeframe=tf,
            final_equity=sim.get_equity(),
            return_pct=(sim.get_equity() - initial_capital) / initial_capital * 100,
            max_drawdown=max_dd,
            trade_count=trades_count,
            win_rate=win_rate,
            profit_factor=pf,
            verdict_counts=v_counts,
            top_block_reasons=[] # Todo: aggregate
        )
        writer.write_summary(summary)
        
        # Chart Marks
        marks = GameChartMarksV1.generate_marks(sim.trades, steps)
        writer.write_chart_marks(marks)
        
        return {
            "run_id": run_id,
            "equity": sim.get_equity(),
            "trades": trades_count
        }
