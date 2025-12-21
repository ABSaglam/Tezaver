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
    MX-2002 + MX-2000.3: WarEngine
    Runs multi-coin backtest with global risk limits.
    MX-2000.3: Supports ERROR_INFRA verdict and retry-safe lifecycle.
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
        
        # MX-2000.3: Cell error tracking
        self.cell_errors: List[Dict] = []
    
    def run(self) -> Dict:
        """
        Execute WAR backtest.
        W2: Returns EMPTY_PLAN error if no cells.
        W3: Updates candidate status based on verdict.
        Returns: run result dict
        """
        start_ts = datetime.now()
        
        # W2: Handle empty plan
        if self.plan.is_empty:
            self._emit_event("WAR_EMPTY_PLAN", {
                "run_id": self.run_id,
                "diagnostics": self.plan.diagnostics.to_dict()
            })
            return {
                "run_id": self.run_id,
                "plan_id": self.plan.plan_id,
                "verdict": "EMPTY_PLAN",
                "scorecard": {},
                "verdict_report": {"verdict": "EMPTY_PLAN", "reasons": ["No APPROVED_FOR_WAR candidates"]},
                "duration_s": 0,
                "artifacts_dir": None,
                "run_created": False,
                "diagnostics": self.plan.diagnostics.to_dict()
            }
        
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
        
        # Get verdict - check for infra errors first
        scorecard_dict = self.scorecard.to_dict()
        
        # MX-2000.3: Check for cell errors before judging
        if self.cell_errors:
            # All cells failed with errors -> ERROR_INFRA
            if len(self.cell_errors) == len(self.plan.cells):
                verdict = "ERROR_INFRA"
                verdict_report = {
                    "verdict": "ERROR_INFRA",
                    "reasons": [f"All {len(self.cell_errors)} cells failed with infra errors"],
                    "cell_errors": self.cell_errors
                }
            else:
                # Some cells succeeded, use normal verdict
                verdict_report = self.judge.generate_report(scorecard_dict)
                verdict = verdict_report["verdict"]
        else:
            verdict_report = self.judge.generate_report(scorecard_dict)
            verdict = verdict_report["verdict"]
        
        # Update registry
        self.registry.update_finished(self.run_id, scorecard_dict, verdict)
        
        # MX-2000.3: Update candidate status only if not ERROR_INFRA
        self._update_candidate_status(verdict)
        
        self._emit_event("WAR_END", {
            "run_id": self.run_id,
            "verdict": verdict,
            "total_trades": scorecard_dict["total_trades"],
            "net_pnl": scorecard_dict["net_pnl"],
            "cell_error_count": len(self.cell_errors)
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
            "artifacts_dir": str(self.output_dir / self.run_id),
            "run_created": True,
            "cell_error_count": len(self.cell_errors)
        }
    
    def _update_candidate_status(self, verdict: str):
        """
        MX-2000.3: Update candidate status based on WAR verdict.
        PASS -> APPROVED_FOR_LIVE
        IMPROVE -> NEEDS_PATCH
        FAIL -> REJECTED_BY_WAR
        ERROR_INFRA -> status retained (APPROVED_FOR_WAR) or NEEDS_RETRY
        """
        from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
        
        # MX-2000.3: ERROR_INFRA means infra issue, not strategy issue
        # Candidate status should be retained for retry
        if verdict == "ERROR_INFRA":
            for candidate_id in self.plan.candidate_ids:
                for cell in self.plan.cells:
                    if cell.candidate_id == candidate_id:
                        self._emit_event("CANDIDATE_STATUS_RETAINED", {
                            "candidate_id": candidate_id,
                            "bundle_id": cell.bundle_id,
                            "status": "APPROVED_FOR_WAR",
                            "reason": "ERROR_INFRA - retry allowed",
                            "run_id": self.run_id
                        })
                        break
            return
        
        status_map = {
            "PASS": "APPROVED_FOR_LIVE",
            "IMPROVE": "NEEDS_PATCH",
            "FAIL": "REJECTED_BY_WAR"
        }
        
        new_status = status_map.get(verdict)
        if not new_status:
            return
        
        candidate_registry = CandidateRegistry()
        
        for candidate_id in self.plan.candidate_ids:
            # Find by bundle_id (which is used as primary key now)
            for cell in self.plan.cells:
                if cell.candidate_id == candidate_id:
                    candidate_registry.update_status(cell.bundle_id, new_status)
                    
                    self._emit_event("CANDIDATE_STATUS_UPDATED", {
                        "candidate_id": candidate_id,
                        "bundle_id": cell.bundle_id,
                        "old_status": "APPROVED_FOR_WAR",
                        "new_status": new_status,
                        "war_source": "WAR",
                        "run_id": self.run_id
                    })
                    break
    
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
            # MX-2000.3: Track cell errors for ERROR_INFRA verdict
            error_info = {
                "candidate_id": cell.candidate_id,
                "symbol": cell.symbol,
                "tf": cell.tf,
                "error_kind": getattr(e, 'error_kind', 'DATA_PORT_ERROR'),
                "error_message": str(e)
            }
            self.cell_errors.append(error_info)
            
            self._emit_event("WAR_CELL_INFRA_ERROR", error_info)
            return
        
        # MX-2000.3: Check if we got any bars
        if not bars:
            error_info = {
                "candidate_id": cell.candidate_id,
                "symbol": cell.symbol,
                "tf": cell.tf,
                "error_kind": "NO_DATA",
                "error_message": f"No bars found for {cell.symbol}/{cell.tf}"
            }
            self.cell_errors.append(error_info)
            self._emit_event("WAR_CELL_INFRA_ERROR", error_info)
            return
        
        # Setup broker for this cell
        broker = SimBroker(
            fee_pct=0.001,
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
        
        # Get trade count for this candidate
        candidate_score = self.scorecard.by_candidate.get(cell.candidate_id)
        trade_count = candidate_score.trades if candidate_score else 0
        
        self._emit_event("CELL_END", {
            "candidate_id": cell.candidate_id,
            "trades_count": trade_count
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
