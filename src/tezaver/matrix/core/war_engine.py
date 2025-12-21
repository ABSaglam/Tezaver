"""
MX-2002: WarEngine - Multi-coin backtest motor for WAR mode.
"""
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from tezaver.matrix.apps.war_planner import WarPlan, WarCell
from tezaver.matrix.core.risk_limiter import RiskLimiter, RiskLimits
from tezaver.matrix.core.war_scorecard import WarScorecard
from tezaver.matrix.core.war_judge import WarJudge, WarGates
from tezaver.matrix.adapters.war_run_registry import WarRunRegistry
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.data_port_parquet import ParquetDataPort


class WarEngine:
    """
    MX-2002: WarEngine
    Runs multi-coin backtest with global risk limits.
    """
    
    def __init__(
        self,
        plan: WarPlan,
        risk_limits: RiskLimits = None,
        gates: WarGates = None,
        output_dir: str = "out/matrix_runs/war",
        seed: int = 42
    ):
        self.plan = plan
        self.risk_limiter = RiskLimiter(risk_limits or RiskLimits())
        self.scorecard = WarScorecard()
        self.judge = WarJudge(gates or WarGates())
        self.registry = WarRunRegistry()
        self.output_dir = Path(output_dir)
        self.seed = seed
        
        # Generate run_id
        run_content = f"{plan.plan_id}_{seed}_{datetime.now().isoformat()}"
        self.run_id = f"war_{hashlib.sha256(run_content.encode()).hexdigest()[:12]}"
        
        # Telemetry
        self.telemetry: List[Dict] = []
        self.trade_audit: List[Dict] = []
    
    def run(self) -> Dict:
        """
        Execute WAR backtest.
        Returns: run result dict
        """
        start_ts = datetime.now()
        
        # Register run as started
        self.registry.register(
            run_id=self.run_id,
            plan_id=self.plan.plan_id,
            candidate_ids=self.plan.candidate_ids,
            symbols=self.plan.symbols,
            config_hash=self.plan.config_hash,
            verdict="RUNNING"
        )
        
        self._emit_event("WAR_START", {
            "run_id": self.run_id,
            "plan_id": self.plan.plan_id,
            "cell_count": len(self.plan.cells),
            "symbols": self.plan.symbols
        })
        
        # Process each cell (candidate)
        for cell in self.plan.cells:
            self._process_cell(cell)
        
        # Finalize scorecard
        self.scorecard.finalize()
        
        # Get verdict
        scorecard_dict = self.scorecard.to_dict()
        verdict_report = self.judge.generate_report(scorecard_dict)
        verdict = verdict_report["verdict"]
        
        # Update registry
        self.registry.update_finished(self.run_id, scorecard_dict, verdict)
        
        self._emit_event("WAR_END", {
            "run_id": self.run_id,
            "verdict": verdict,
            "total_trades": scorecard_dict["total_trades"],
            "net_pnl": scorecard_dict["net_pnl"]
        })
        
        # Save artifacts
        self._save_artifacts(scorecard_dict, verdict_report)
        
        end_ts = datetime.now()
        
        return {
            "run_id": self.run_id,
            "plan_id": self.plan.plan_id,
            "verdict": verdict,
            "scorecard": scorecard_dict,
            "verdict_report": verdict_report,
            "duration_s": (end_ts - start_ts).total_seconds(),
            "artifacts_dir": str(self.output_dir / self.run_id)
        }
    
    def _process_cell(self, cell: WarCell):
        """Process a single cell (candidate) in the WAR run."""
        self._emit_event("CELL_START", {
            "candidate_id": cell.candidate_id,
            "symbol": cell.symbol,
            "tf": cell.tf
        })
        
        # Load data
        try:
            data_port = ParquetDataPort(cell.symbol, cell.tf)
            bars = data_port.get_bars(limit=500)  # Configurable
        except Exception as e:
            self._emit_event("CELL_ERROR", {
                "candidate_id": cell.candidate_id,
                "error": str(e)
            })
            return
        
        # Setup broker for this cell
        broker = SimBroker(
            initial_balance=10000.0,
            fee_rate=0.001,
            slippage_pct=0.0005
        )
        
        # Simulate trades (simplified - real implementation would use strategy)
        position_open = False
        entry_price = 0.0
        entry_ts = 0
        
        for i, bar in enumerate(bars):
            ts = bar.get("timestamp", i)
            close = bar.get("close", 0)
            
            if not position_open:
                # Check risk limits before opening
                notional = close * 0.1  # 10% position size
                allowed, block_reason = self.risk_limiter.check_order(
                    cell.symbol, notional, cell.candidate_id, ts
                )
                
                if not allowed:
                    self._emit_event("RISK_BLOCK", {
                        "candidate_id": cell.candidate_id,
                        "symbol": cell.symbol,
                        "reason": block_reason
                    })
                    self.scorecard.record_risk_block()
                    continue
                
                # Open position (simplified trigger - every 50 bars)
                if i % 50 == 10:
                    position_open = True
                    entry_price = close
                    entry_ts = ts
                    self.risk_limiter.open_position(cell.symbol, notional, cell.candidate_id, ts)
                    
                    self._emit_event("POSITION_OPEN", {
                        "candidate_id": cell.candidate_id,
                        "symbol": cell.symbol,
                        "price": close
                    })
            else:
                # Close position (simplified - after 20 bars)
                if (i - (entry_ts if isinstance(entry_ts, int) else 0)) % 50 == 30:
                    exit_price = close
                    pnl = (exit_price - entry_price) / entry_price * 100  # % PnL
                    fee = abs(pnl) * 0.001
                    slippage = abs(pnl) * 0.0005
                    is_win = pnl > 0
                    
                    self.scorecard.record_trade(
                        cell.candidate_id, cell.symbol, pnl, fee, slippage, is_win
                    )
                    
                    self.trade_audit.append({
                        "ts": ts,
                        "candidate_id": cell.candidate_id,
                        "symbol": cell.symbol,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "fee": fee,
                        "slippage": slippage
                    })
                    
                    self._emit_event("POSITION_CLOSE", {
                        "candidate_id": cell.candidate_id,
                        "symbol": cell.symbol,
                        "pnl": pnl
                    })
                    
                    self.risk_limiter.close_position(cell.symbol)
                    position_open = False
        
        self._emit_event("CELL_END", {
            "candidate_id": cell.candidate_id,
            "trades": self.scorecard.by_candidate.get(cell.candidate_id, {})
        })
    
    def _emit_event(self, kind: str, data: Dict):
        """Emit telemetry event."""
        event = {
            "ts": datetime.now().isoformat(),
            "kind": kind,
            "run_id": self.run_id,
            **data
        }
        self.telemetry.append(event)
    
    def _save_artifacts(self, scorecard: Dict, verdict_report: Dict):
        """Save all artifacts to output directory."""
        run_dir = self.output_dir / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Report
        report = {
            "run_id": self.run_id,
            "plan": self.plan.to_dict(),
            "verdict": verdict_report["verdict"],
            "risk_summary": self.risk_limiter.get_summary(),
            "created_at": datetime.now().isoformat()
        }
        with open(run_dir / "report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Scorecard
        with open(run_dir / "scorecard.json", "w") as f:
            json.dump(scorecard, f, indent=2)
        
        # Telemetry
        with open(run_dir / "telemetry.ndjson", "w") as f:
            for event in self.telemetry:
                f.write(json.dumps(event) + "\n")
        
        # Trade audit
        with open(run_dir / "trade_audit_v2.jsonl", "w") as f:
            for trade in self.trade_audit:
                f.write(json.dumps(trade) + "\n")
