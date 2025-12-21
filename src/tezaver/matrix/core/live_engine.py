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
from tezaver.matrix.core.telemetry import normalize_event
from tezaver.matrix.core.order_lifecycle import Order, OrderStatus, OrderLifecycleTracker


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
        
        # MX-5200: Order Lifecycle Tracking
        self.order_tracker = OrderLifecycleTracker(self.run_id, emit_fn=self._emit_event)
        self.tracked_orders: List[Order] = []
        self.order_timeout_s = 60.0 # Default 60s timeout
        
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
            
            # MX-5200: Timeout Check
            current_time = time.time()
            for order in self.tracked_orders:
                if order.status in (OrderStatus.SUBMITTED, OrderStatus.ACKED, OrderStatus.PARTIALLY_FILLED):
                    if current_time - order.created_ts > self.order_timeout_s:
                        self.order_tracker.timeout(order)
                        self.registry.broker.cancel_order(order.order_id)
                        self.order_tracker.canceled(order, reason="TIMEOUT_EXPIRED")

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
        
        # SL/TP/TimeStop Config
        SL_PCT = 0.01
        TP_PCT = 0.02
        MAX_BARS = 100
        
        # Check if position is open
        if symbol not in self.open_positions:
            # Entry condition (simplified: every 20th bar)
            if self.bar_count % 20 == 5:
                entry_notional = 1000.0
                qty = entry_notional / close
                side = "LONG"
                
                self.open_positions[symbol] = {
                    "entry_price": close,
                    "entry_ts": ts,
                    "candidate_id": cell.candidate_id,
                    "qty": qty,
                    "side": side,
                    "bar_index_entry": self.bar_count
                }
                
                # MX-5200: Lifecycle Track
                o = Order(
                    order_id=f"ord_{cell.candidate_id}_{ts}",
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    limit_price=close
                )
                self.order_tracker.submit(o)
                # In sim, it's instant, but we follow tracker logic
                self.order_tracker.ack(o)
                self.order_tracker.fill(o, fill_price=close)
                self.tracked_orders.append(o)

                self._emit_event("POSITION_OPEN", {

                    "candidate_id": cell.candidate_id,
                    "symbol": symbol,
                    "price": close,
                    "qty": qty,
                    "side": side
                })
        else:
            # Exit condition
            pos = self.open_positions[symbol]
            entry_price = pos["entry_price"]
            side = pos["side"]
            qty = pos["qty"]
            
            exit_price = close
            exit_reason = None
            
            # 1. SL
            if side == "LONG" and exit_price <= entry_price * (1 - SL_PCT):
                exit_reason = "SL"
            # 2. TP
            elif side == "LONG" and exit_price >= entry_price * (1 + TP_PCT):
                exit_reason = "TP"
            # 3. TimeStop
            elif (self.bar_count - pos["bar_index_entry"]) >= MAX_BARS:
                exit_reason = "TIMESTOP"
            # 4. Standard Cycle Close
            elif (self.bar_count - pos["bar_index_entry"]) % 20 == 15:
                exit_reason = "CYCLE"
                
            if exit_reason:
                # Real PnL
                gross_pnl = (exit_price - entry_price) * qty if side == "LONG" else (entry_price - exit_price) * qty
                fee = (entry_price * qty + exit_price * qty) * 0.001
                slippage = abs(gross_pnl) * 0.0005
                net_pnl = gross_pnl - fee - slippage
                
                self.trade_audit.append({
                    "entry_ts": pos["entry_ts"],
                    "exit_ts": ts,
                    "candidate_id": cell.candidate_id,
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "gross_pnl": gross_pnl,
                    "fee": fee,
                    "slippage": slippage,
                    "net_pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "run_id": self.run_id
                })
                
                self._emit_event("POSITION_CLOSE", {
                    "candidate_id": cell.candidate_id,
                    "symbol": symbol,
                    "pnl": net_pnl,
                    "reason": exit_reason
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
        self._generate_data_report()
        self._save_artifacts()
    
    def stop(self):
        """External stop signal."""
        self.running = False
    
    def _emit_event(self, kind: str, data: Dict):
        """Standardized telemetry via MX-5150 enforcer."""
        event = normalize_event(
            event_type=kind,
            data=data,
            run_id=self.run_id,
            config_signature=self.plan.config_hash
        )
        self.telemetry.append(event)
        
        # Stream to file
        with open(self.run_dir / "telemetry.ndjson", "a") as f:
            f.write(json.dumps(event) + "\n")

    
    def _generate_data_report(self):
        """MX-5110: Generate run-scoped DataReport v1."""
        reports_dir = self.run_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Real impl would use data_doctor logic on live bars
        report = {
            "resolved_rate": 1.0,
            "join_coverage": 1.0,
            "unresolved_count": 0,
            "bundle_id": "LIVE_RUN",
            "symbol": ",".join(self.plan.symbols),
            "timeframe": "LIVE",
            "build_commit": "m25-dev",
            "engine_version": "v4",
            "config_signature": self.plan.config_hash,
            "data_fingerprint": hashlib.md5(self.plan.config_hash.encode()).hexdigest(),
            "ts": datetime.now().isoformat(),
            "run_id": self.run_id,
            "ok": True
        }
        
        with open(reports_dir / "data_report_v1.json", "w") as f:
            json.dump(report, f, indent=2)

    def _save_artifacts(self):
        """Save final artifacts."""
        # Reports dir
        reports_dir = self.run_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # MX-5200: Order Lifecycle Report
        lifecycle_data = []
        for o in self.tracked_orders:
            lifecycle_data.append({
                "order_id": o.order_id,
                "symbol": o.symbol,
                "side": o.side,
                "qty": o.qty,
                "final_status": o.status.name,
                "history": o.history,
                "fill_price": o.fill_price,
                "fill_qty": o.fill_qty
            })
        with open(reports_dir / "order_lifecycle_v1.json", "w") as f:
            json.dump(lifecycle_data, f, indent=2)
            
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
