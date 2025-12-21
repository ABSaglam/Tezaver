"""
MX-3002: LiveEngine - Closed-bar loop motor for LIVE mode.
"""
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from tezaver.matrix.apps.live_planner import LivePlan, LiveCell
from tezaver.matrix.adapters.live_run_registry import LiveRunRegistry
from tezaver.matrix.core.live_reconciliation import LiveReconciliation
from tezaver.matrix.apps.incident_bundle import IncidentBundle
from tezaver.matrix.adapters.broker_sim import SimBroker


class LiveEngine:
    """
    MX-3002: LiveEngine
    Runs closed-bar loop for LIVE trading.
    """
    
    def __init__(
        self,
        plan: LivePlan,
        output_dir: str = "out/matrix_runs/live",
        safe_mode: bool = False,
        bar_callback: Callable = None
    ):
        self.plan = plan
        self.output_dir = Path(output_dir)
        self.safe_mode = safe_mode
        self.bar_callback = bar_callback  # For fake feed injection
        
        # Generate run_id
        run_content = f"{plan.plan_id}_{datetime.now().isoformat()}"
        self.run_id = f"live_{hashlib.sha256(run_content.encode()).hexdigest()[:12]}"
        
        # Registries
        self.registry = LiveRunRegistry()
        self.reconciliation = LiveReconciliation()
        self.incident_bundle = IncidentBundle()
        
        # State
        self.running = False
        self.bar_count = 0
        self.trade_count = 0
        self.telemetry: List[Dict] = []
        self.trade_audit: List[Dict] = []
        self.open_positions: Dict[str, Dict] = {}  # symbol -> position
        
        # Setup output dir
        self.run_dir = self.output_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self, max_bars: int = None) -> Dict:
        """
        Start LIVE loop.
        max_bars: for testing - stop after N bars (None = infinite)
        """
        # Empty plan check
        if self.plan.is_empty:
            self._emit_event("LIVE_EMPTY_PLAN", {})
            return {
                "run_id": self.run_id,
                "status": "EMPTY_PLAN",
                "bar_count": 0,
                "trade_count": 0
            }
        
        # Reconciliation check
        recon_result = self.reconciliation.check(self.run_id)
        if recon_result.safe_mode_required:
            self.safe_mode = True
            self._emit_event("LIVE_SAFE_MODE_ENABLED", {
                "reason": "reconciliation_error",
                "issues": recon_result.issues
            })
        
        # Add reconciliation telemetry
        self.telemetry.extend(self.reconciliation.get_telemetry())
        
        # Register run
        self.registry.register(
            run_id=self.run_id,
            plan_id=self.plan.plan_id,
            cells=self.plan.cells,
            symbols=self.plan.symbols,
            config_hash=self.plan.config_hash,
            safe_mode=self.safe_mode
        )
        
        self._emit_event("LIVE_START", {
            "run_id": self.run_id,
            "plan_id": self.plan.plan_id,
            "cell_count": len(self.plan.cells),
            "safe_mode": self.safe_mode
        })
        
        self.running = True
        
        try:
            self._run_loop(max_bars)
        except Exception as e:
            self._handle_exception(e)
        finally:
            self._stop()
        
        return {
            "run_id": self.run_id,
            "status": "STOPPED",
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "safe_mode": self.safe_mode
        }
    
    def _run_loop(self, max_bars: int = None):
        """Main closed-bar loop."""
        while self.running:
            # Get next bar (from callback or wait)
            if self.bar_callback:
                bars = self.bar_callback(self.bar_count)
                if bars is None:
                    # No more bars
                    break
            else:
                # Real-time: wait for next bar close
                time.sleep(1)  # Placeholder
                bars = {}  # Would come from live feed
            
            # Process closed bars
            self._process_bar(bars)
            
            self.bar_count += 1
            
            # Heartbeat
            self.registry.update_heartbeat(self.run_id, self.bar_count, self.trade_count)
            
            # Max bars check (for testing)
            if max_bars and self.bar_count >= max_bars:
                break
    
    def _process_bar(self, bars: Dict):
        """Process a closed bar for all cells."""
        self._emit_event("BAR_CLOSED", {
            "bar_index": self.bar_count
        })
        
        for cell in self.plan.cells:
            self._process_cell_bar(cell, bars.get(cell.symbol, {}))
    
    def _process_cell_bar(self, cell: LiveCell, bar: Dict):
        """Process bar for single cell - closed-bar only decision."""
        if not bar:
            return
        
        # SAFE_MODE: no new orders
        if self.safe_mode:
            self._emit_event("CELL_SKIP_SAFE_MODE", {
                "candidate_id": cell.candidate_id,
                "symbol": cell.symbol
            })
            return
        
        # Simplified trading logic
        broker = SimBroker(fee_pct=0.001, slippage_pct=0.0005)
        
        symbol = cell.symbol
        close = bar.get("close", 0)
        ts = bar.get("timestamp", self.bar_count)
        
        # Check if position is open
        if symbol not in self.open_positions:
            # Entry condition (simplified: every 10th bar)
            if self.bar_count % 10 == 5:
                self.open_positions[symbol] = {
                    "entry_price": close,
                    "entry_ts": ts,
                    "candidate_id": cell.candidate_id
                }
                self._emit_event("POSITION_OPEN", {
                    "candidate_id": cell.candidate_id,
                    "symbol": symbol,
                    "price": close
                })
        else:
            # Exit condition (simplified: after 5 bars)
            pos = self.open_positions[symbol]
            if (self.bar_count - self.bar_count % 10) % 10 == 0:
                pnl = (close - pos["entry_price"]) / pos["entry_price"] * 100
                fee = abs(pnl) * 0.001
                
                self.trade_audit.append({
                    "ts": ts,
                    "candidate_id": cell.candidate_id,
                    "symbol": symbol,
                    "entry_price": pos["entry_price"],
                    "exit_price": close,
                    "pnl": pnl,
                    "fee": fee
                })
                
                self._emit_event("POSITION_CLOSE", {
                    "candidate_id": cell.candidate_id,
                    "symbol": symbol,
                    "pnl": pnl
                })
                
                del self.open_positions[symbol]
                self.trade_count += 1
        
        # Save state for reconciliation
        self.reconciliation.save_state(
            self.run_id,
            list(self.open_positions.values()),
            []  # No open orders in simplified impl
        )
    
    def _handle_exception(self, e: Exception):
        """Handle exception and create incident bundle."""
        self._emit_event("LIVE_ERROR", {
            "error": str(e),
            "error_type": type(e).__name__
        })
        
        incident_id = self.incident_bundle.create(
            run_id=self.run_id,
            incident_type="EXCEPTION",
            telemetry_events=self.telemetry,
            config=self.plan.to_dict(),
            exception=e
        )
        
        self.registry.increment_incident(self.run_id)
        
        self._emit_event("INCIDENT_CREATED", {
            "incident_id": incident_id
        })
    
    def _stop(self):
        """Stop the engine and save artifacts."""
        self.running = False
        
        self._emit_event("LIVE_STOP", {
            "run_id": self.run_id,
            "bar_count": self.bar_count,
            "trade_count": self.trade_count
        })
        
        # Update registry status
        self.registry.update_status(self.run_id, "STOPPED")
        
        # Clear reconciliation state (clean shutdown)
        if not self.open_positions:
            self.reconciliation.clear_state()
        
        # Save artifacts
        self._save_artifacts()
    
    def stop(self):
        """External stop signal."""
        self.running = False
    
    def _emit_event(self, kind: str, data: Dict):
        """Emit telemetry event."""
        event = {
            "ts": datetime.now().isoformat(),
            "kind": kind,
            "run_id": self.run_id,
            **data
        }
        self.telemetry.append(event)
        
        # Stream to file
        with open(self.run_dir / "telemetry.ndjson", "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def _save_artifacts(self):
        """Save final artifacts."""
        # Report
        report = {
            "run_id": self.run_id,
            "plan": self.plan.to_dict(),
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "safe_mode": self.safe_mode,
            "stopped_at": datetime.now().isoformat()
        }
        with open(self.run_dir / "report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Trade audit
        with open(self.run_dir / "trade_audit_v2.jsonl", "w") as f:
            for trade in self.trade_audit:
                f.write(json.dumps(trade) + "\n")
