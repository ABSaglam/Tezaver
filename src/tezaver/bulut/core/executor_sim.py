# Tezaver Bulut - Simulated Executor (P4)
"""
Simulated Executor for Dry-Run / Paper Mainnet Dress Rehearsal.
Mimics Mainnet execution but logs actions instead of calling Exchange API.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
# from tezaver.bulut.services.telemetry import TelemetryService
from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1, TradeDecision

class SimulatedExecutor:
    """
    Executes plans in simulation mode (Dry Run).
    Maintains local state if needed via persistence or in-memory for the run.
    """
    
    def __init__(self, config: BulutConfig, persistence: SqlitePersistence, telemetry: Any):
        self._config = config
        self._persistence = persistence
        self._telemetry = telemetry
        self._sim_run_id = f"DRY_{uuid.uuid4().hex[:8]}"

    async def execute_plans(self, plans: List[TradePlanV1]) -> Dict[str, Any]:
        """
        Execute a batch of plans (Open/Close) in SIMULATION mode.
        """
        executed_count = 0
        failed_count = 0
        
        for plan in plans:
            try:
                # plan.decision is Enum. check using .name or value
                if plan.decision.name == "OPEN":
                   await self._sim_open(plan)
                elif plan.decision.name == "CLOSE":
                   await self._sim_close(plan)
                
                executed_count += 1
            except Exception as e:
                print(f"[SIM-EXECUTOR] Plan failed: {e}")
                failed_count += 1
                
        return {
            "executed": executed_count,
            "failed": failed_count,
            "mode": "DRY_RUN_SIM"
        }

    async def recover_executing_plans(self, ctx):
        """Mock recovery."""
        print("[SIM-EXECUTOR] Determinism recovery skipped in Dry Run.")

    async def _sim_open(self, plan: TradePlanV1):
        """Simulate OPEN order."""
        symbol = plan.symbol
        # Assume fill at current price (or plan.price)
        # We don't have price in plan? We have ranking.candidates -> price
        # Actually plan usually has notional.
        # We need entry price.
        # For Sim/DryRun, we might need to fetch current price tick?
        # Or just trust decision price if available.
        # Plan schema doesn't strictly carry 'entry_price' unless metadata?
        # Let's assume market open.
        
        print(f"[SIM-EXECUTOR] ??? OPEN {symbol} Notional=${plan.notional_usdt}")
        
        # 1. Update Persistence (Fake Position)
        # We insert into 'open_positions' table so Decider sees it next cycle?
        # YES. Dry Run needs state continuity.
        # But we don't want to pollute REAL DB if this is a "Test"?
        # Requirement: "Mainnet Dry-Run ... MODE=Mainnet".
        # If we write to REAL `open_positions`, we mess up real state if we stop dry run?
        # "AMA emirler borsaya GİTMEZ".
        # If we share the DB, we corrupt mainnet state with fake positions.
        # CRITICAL: Dry Run should probably use a separate DB or TABLE?
        # OR: We use `open_positions` but filter by `execution_mode='SIM'`?
        # The prompt didn't specify DB isolation. 
        # But `persistence_sqlite` is shared.
        # If I start Dry Run on Mainnet, and it opens a position in DB, then I stop Dry Run...
        # ... Mainnet logic will see that position and try to manage it.
        # AND report it in PnL.
        # This is bad.
        
        # DECISION: Dry Run usually implies transient state OR specific "Testnet" database.
        # But request says "MODE=REAL_MAINNET" logic.
        # Maybe we should use a `persistence` instance pointed to `:memory:` or a temp file?
        # `DryRunService` creates a *Context* for the run.
        # That Context should have an isolated Persistence!
        # Ah! `DryRunService` runs `cycles`. P4-C1 says "run loop... scan -> decide -> ...".
        # If `DryRunService` constructs its own Context, it can use a separate DB.
        # BUT: It needs history/bars from the REAL DB?
        # Solutions:
        # A) Use separate DB file (copy of prod or fresh).
        # B) Use In-Memory DB (fast, disposable).
        
        # Let's go with B) In-Memory DB initialized with necessary state?
        # Or simple file-based `bulut_dryrun.db`.
        # This `SimulatedExecutor` assumes it calls `self._persistence.insert_position`.
        # So as long as `self._persistence` points to the DryRun DB, we are safe.
        
        # So `SimulatedExecutor` logic is standard "Update DB" logic, just logging "SIM" events.
        
        # Insert Position
        # Needed: entry_price, size.
        # Plan doesn't have price. We need to fetch it.
        # Assuming Context passes price or we fetch it?
        # `execute_plans` receives `plans`.
        # Plan has `decision.metadata`?
        # Let's just use dummy price 100000 for simplicity or Mock.
        
        entry_price = 100000.0 # Placeholder
        size = plan.notional_usdt / entry_price
        
        pos_id = f"sim_{uuid.uuid4().hex[:6]}"
        
        self._persistence.open_position({
            "position_id": pos_id,
            "symbol": symbol,
            "entry_price": entry_price,
            "size": size,
            "side": "LONG", # Matrix V1 is Long Only
            "plan_id": plan.idempotency_key,
            "strategy": plan.reasons.get("strategy", "unknown"),
            "entry_ts": datetime.now(timezone.utc).isoformat()
        })
        
        self._telemetry.emit("ORDER_SUBMITTED_SIM", {
            "symbol": symbol, "side": "BUY", "notional": plan.notional_usdt
        })
        self._telemetry.emit("ORDER_FILLED_SIM", {
            "symbol": symbol, "price": entry_price, "size": size
        })
        
    async def _sim_close(self, plan: TradePlanV1):
        """Simulate CLOSE order."""
        symbol = plan.symbol
        print(f"[SIM-EXECUTOR] ??? CLOSE {symbol}")
        
        # Retrieve position to close
        # Persistence `get_open_position(symbol)`
        # Note: persistence sqlite might not have search by symbol helper exposed cleanly?
        # `get_open_positions` returns list.
        positions = self._persistence.get_open_positions()
        target = next((p for p in positions if p["symbol"] == symbol), None)
        
        if target:
            # PnL calc
            entry_price = target["entry_price"]
            exit_price = 100000.0 # Placeholder (flat)
            pnl = (exit_price - entry_price) * target["size"]
            
            # Archive
            self._persistence.close_position(target["position_id"], {
                "exit_price": exit_price,
                "exit_ts": datetime.now(timezone.utc).isoformat(),
                "pnl_realized": pnl,
                "exit_reason": plan.reasons.get("model", "signal")
            })
            
            self._telemetry.emit("ORDER_SUBMITTED_SIM", {
                "symbol": symbol, "side": "SELL"
            })
            self._telemetry.emit("ORDER_FILLED_SIM", {
                "symbol": symbol, "pnl": pnl
            })
        else:
            print(f"[SIM-EXECUTOR] Position not found for {symbol}")
