# Tezaver Bulut - NDJSON Telemetry Service
"""
NDJSON-based telemetry for Bulut events.
Each line is a standalone JSON event.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class NdjsonTelemetry:
    """
    NDJSON telemetry writer for Tezaver Bulut.
    
    Event types:
    - RANKING_SNAPSHOT: Emitted after each scan cycle
    - TRADE_PLAN: Emitted for each trade decision
    - TRADE_LOCKED: Emitted when trade is blocked
    - SYSTEM_EVENT: General system events
    """
    
    def __init__(self, ndjson_path: str):
        self._path = Path(ndjson_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
    
    def emit(self, event_type: str, data: dict) -> None:
        """Emit a telemetry event."""
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **data,
        }
        self._write(event)
    
    def emit_ranking_snapshot(self, snapshot_dict: dict) -> None:
        """
        Emit RANKING_SNAPSHOT event.
        """
        self.emit("RANKING_SNAPSHOT", {
            "schema": snapshot_dict.get("schema", "ranking_snapshot_v1"),
            "cycle_ts": snapshot_dict.get("cycle_ts"),
            "snapshot": snapshot_dict,
            "shortlist_count": len(snapshot_dict.get("candidates", [])),
        })
    
    def emit_trade_plan_proposed(self, plan: dict) -> None:
        """Emit TRADE_PLAN_PROPOSED."""
        self.emit("TRADE_PLAN_PROPOSED", {
            "symbol": plan.get("symbol"),
            "decision": plan.get("decision"),
            "reasons": plan.get("reasons"),
            "plan_id": plan.get("idempotency_key"),
            "plan": plan
        })

    def emit_execution_blocked(self, data: Dict[str, Any]):
        """Emit execution blocked event."""
        self.emit("EXECUTION_BLOCKED", data)

    def emit_exit_profiles_bootstrap(self, data: Dict[str, Any]):
        """Emit exit profiles bootstrap event."""
        self.emit("EXIT_PROFILES_BOOTSTRAP", data)

    def emit_protective_orders_placed(self, data: Dict[str, Any]):
        """Emit protective orders placed."""
        self.emit("PROTECTIVE_ORDERS_PLACED", data)

    def emit_protective_orders_cancelled(self, data: Dict[str, Any]):
        """Emit protective orders cancelled."""
        self.emit("PROTECTIVE_ORDERS_CANCELLED", data)

    def emit_exchangeinfo_refresh(self, ok: bool, details: Dict[str, Any]):
        """Emit exchange info refresh status."""
        event = "EXCHANGEINFO_REFRESH_OK" if ok else "EXCHANGEINFO_REFRESH_FAIL"
        self.emit(event, details)

    def emit_filters_missing(self, symbol: str, where: str):
        """Emit filters missing event."""
        self.emit("FILTERS_MISSING", {"symbol": symbol, "where": where})

    def emit_filters_violation(self, symbol: str, reason: str):
        """Emit filters violation event."""
        self.emit("FILTERS_VIOLATION", {"symbol": symbol, "reason": reason})

    def emit_trade_plan_blocked(self, plan: dict, reason: str) -> None:
        """Emit TRADE_PLAN_BLOCKED."""
        self.emit("TRADE_PLAN_BLOCKED", {
            "symbol": plan.get("symbol"),
            "block_reason": reason,
            "decision": plan.get("decision"),
            "plan_id": plan.get("idempotency_key")
        })

    def emit_trade_plan_accepted(self, plan: dict, mode: str = "AUTO") -> None:
        """Emit TRADE_PLAN_ACCEPTED."""
        self.emit("TRADE_PLAN_ACCEPTED", {
            "symbol": plan.get("symbol"),
            "mode": mode,
            "plan_id": plan.get("idempotency_key"),
            "notional": plan.get("notional_usdt")
        })
    
    def emit_trade_locked(self, symbol: str, lock_reason: str) -> None:
        """Emit TRADE_LOCKED event."""
        self.emit("TRADE_LOCKED", {
            "symbol": symbol,
            "lock_reason": lock_reason,
        })
    
    def emit_system_event(self, event_name: str, details: dict = None) -> None:
        """Emit general system event."""
        self.emit("SYSTEM_EVENT", {
            "name": event_name,
            "details": details or {},
        })
    
    def emit_pattern_pack_loaded(self, pack_id: str, pack_hash: str, symbol_count: int) -> None:
        """Emit PATTERN_PACK_LOADED event."""
        self.emit("PATTERN_PACK_LOADED", {
            "pack_id": pack_id,
            "pack_hash": pack_hash,
            "symbol_count": symbol_count,
        })
    
    def emit_scan_cycle(
        self,
        cycle_ts: datetime,
        universe_size: int,
        shortlist_size: int,
        duration_ms: float,
    ) -> None:
        """Emit SCAN_CYCLE event."""
        self.emit("SCAN_CYCLE", {
            "cycle_ts": cycle_ts.isoformat() if isinstance(cycle_ts, datetime) else cycle_ts,
            "universe_size": universe_size,
            "shortlist_size": shortlist_size,
            "duration_ms": round(duration_ms, 2),
        })
    
    def _write(self, event: dict) -> None:
        """Write event to NDJSON file."""
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str, ensure_ascii=False) + "\n")
        except Exception as e:
            # Telemetry should never crash the system
            print(f"[TELEMETRY_ERROR] {e}")
    
    def read_last_n(self, n: int = 100) -> list[dict]:
        """Read last N events from file."""
        if not self._path.exists():
            return []
        
        events = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for line in lines[-n:]:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        
        return events
    
    def get_last_event_of_type(self, event_type: str) -> Optional[dict]:
        """Get most recent event of a specific type."""
        events = self.read_last_n(500)
        for event in reversed(events):
            if event.get("event_type") == event_type:
                return event
        return None
