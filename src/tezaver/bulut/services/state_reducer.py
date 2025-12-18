# Tezaver Bulut - State Reducer
"""
Unified State Reducer.
Handles deduplication and Out-of-Order protection for state updates.
Merging updates from User Data Stream (WebSocket) and REST polling.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class StateReducer:
    def __init__(
        self, 
        config: BulutConfig,
        persistence: SqlitePersistence,
        telemetry: NdjsonTelemetry
    ):
        self._config = config
        self._persistence = persistence
        self._telemetry = telemetry
        self._duplicates_count = 0
        self._ooo_ignored_count = 0
        self._last_event_ts = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get reducer statistics."""
        return {
            "duplicates": self._duplicates_count,
            "ooo_ignored": self._ooo_ignored_count,
            "last_event_ts_ago": self._last_event_ts
        }

    def apply_order_update(self, event: Dict[str, Any], source: str) -> bool:
        """
        Apply ORDER update (Fill or Status Change).
        event: normalized dict or raw 'o' payload from WS.
        source: 'USER_DATA' | 'REST'
        """
        # Extract ID for dedup
        # WS Payload 'o': i=orderId, s=symbol, T=transactTime
        order_id = str(event.get("i"))
        symbol = event.get("s")
        event_time = int(event.get("T", 0))
        exec_type = event.get("x") # TRADE, NEW, CANCELED
        status = event.get("X")
        
        if not (order_id and symbol):
            return False
            
        # Event ID: Kind + Symbol + OrderId + Status + ExecType + Time
        # More granular than just OrderID because status changes happen to same order.
        event_key = f"ORDER:{symbol}:{order_id}:{exec_type}:{status}:{event_time}"
        
        if not self._check_and_mark(event_key, event_time, source, "ORDER", symbol):
            return False

        # Apply using Persistence
        # Upsert Trade Audit
        # (This logic was inside user_data_stream previously)
        self._persistence.upsert_trade_audit_event(
            order_id=order_id,
            client_id=event.get("c"),
            symbol=symbol,
            status=status,
            exec_type=exec_type,
            filled_qty=float(event.get("z", 0)),
            avg_price=float(event.get("ap", 0)),
            event_time=event_time
        )
        
        self._telemetry.emit("STATE_REDUCER_APPLIED", {
            "kind": "ORDER", "id": order_id, "symbol": symbol, "source": source
        })
        return True

    def apply_account_update(self, event: Dict[str, Any], source: str) -> bool:
        """
        Apply ACCOUNT update (Positions).
        event raw 'a' payload from WS: {P: [...]}
        """
        # Event ID? Account update is frequent. 
        # Usually has 'E' event time in parent payload, or we use 'u' update time?
        # WS Payload: 'E': event time. 'a': { 'm': reason, 'P': positions }
        # We need the parent E time passed in or extracted.
        # Assuming `event` is the full WS payload or 'a' with injected 'E'?
        # Let's assume passed 'event' is 'a' payload + injected '_E' (event ts) or similar?
        # Or we act on specific positions inside?
        # Better: pass full Positions List wrapper.
        
        event_ts = int(event.get("_E", 0)) # We expect caller to inject timestamp
        if event_ts == 0:
            # Fallback current time if missing?
            event_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # We process each position
        positions = event.get("P", [])
        applied_any = False
        
        for p in positions:
            symbol = p.get("s")
            amt = float(p.get("pa", 0))
            
            # Per-position Dedup? 
            # Account updates are snapshots. 
            # We care about OOO more than dedup (idempotent update is fine).
            # But we deduplicate the "Batch" update.
            # Batch ID: ACCOUNT:{event_ts}
            # Actually account updates for different symbols might come.
            # Let's trust OOO on db layer (last_update_ts_ms).
            
            # Logic:
            # If amt == 0 -> Close
            # If amt != 0 -> Upsert (Open/Update)
            
            if amt == 0:
                self._persistence.mark_position_closed(
                    symbol=symbol,
                    close_ts=datetime.fromtimestamp(event_ts/1000.0, timezone.utc),
                    exit_price=0.0, # Unknown in Acc Update
                    exit_reason="EVENT_CLOSED",
                    last_update_ts_ms=event_ts
                )
            else:
                self._persistence.upsert_position_open(
                    symbol=symbol,
                    entry_ts=datetime.fromtimestamp(event_ts/1000.0, timezone.utc), # Approx, logic usually uses trade time
                    entry_price=float(p.get("ep", 0)),
                    qty=amt,
                    notional=abs(amt) * float(p.get("ep", 0)), # Approx
                    sl_pct=0, tp_pct=0, # Unknown
                    last_update_ts_ms=event_ts
                )
            applied_any = True
            
        if applied_any:
            self._telemetry.emit("STATE_REDUCER_APPLIED", {
                "kind": "ACCOUNT", "count": len(positions), "source": source
            })
            
        return True

    def apply_plan_transition(
        self, 
        plan_id: str, 
        to_state: str, 
        decision_id: str, 
        ts_ms: int,
        result: str = None,
        reason: str = None
    ) -> bool:
        """
        Apply Plan State Transition (Determinism Bridge).
        Enforces Exactly-Once and OOO protection.
        """
        # Event ID: PLAN:{plan_id}:{to_state}:{decision_id}
        # Including decision_id ensures we key off the deterministic run.
        event_id = f"PLAN:{plan_id}:{to_state}:{decision_id}"
        
        if not self._check_and_mark(event_id, ts_ms, "INTERNAL", "PLAN", plan_id):
            return False
            
        # OOO Protection
        # We query current state to ensure we don't regress from Final -> Active
        current_plan = self._persistence.get_plan(plan_id)
        if current_plan:
            # Assuming current_plan is dict or object
            # persistence_sqlite.get_plan returns dict usually.
            curr_status = current_plan.get("status") if isinstance(current_plan, dict) else getattr(current_plan, "status", "")
            
            final_states = {"EXECUTED", "FAILED", "BLOCKED_FILTERS", "FAILED_NO_PRICE", "FAILED_API_ERROR", "FAILED_EXEC_ERROR"}
            # Simplify: If current is finalized (not NEW/READY/EXECUTING), ignore updates to EXECUTING
            
            # Simple list of "Done" states
            is_done = curr_status in ["EXECUTED", "FAILED"] or curr_status.startswith("FAILED_") or curr_status.startswith("BLOCKED_")
            
            if is_done and to_state == "EXECUTING":
                 self._ooo_ignored_count += 1
                 self._telemetry.emit("STATE_OOO_IGNORED", {"id": event_id, "curr": curr_status, "to": to_state})
                 return False
                 
        # Apply
        if to_state in ["EXECUTED", "FAILED"] or to_state.startswith("FAILED_") or to_state.startswith("BLOCKED_"):
             # Finalize
             status_cat = "EXECUTED" if to_state == "EXECUTED" else "FAILED"
             if to_state != "EXECUTED" and to_state != "FAILED":
                 self._persistence.update_plan_status(plan_id, to_state)
                 
             self._persistence.finalize_plan_execution(plan_id, status_cat, result or reason)
        else:
             self._persistence.update_plan_status(plan_id, to_state)

        self._telemetry.emit("EXEC_TRANSITION", {
            "plan_id": plan_id,
            "to": to_state,
            "event_id": event_id
        })
        return True

    def _check_and_mark(self, event_id: str, ts_ms: int, source: str, kind: str, symbol: str) -> bool:
        """Helper to dedup."""
        self._last_event_ts = ts_ms
        if self._persistence.try_mark_event_applied(event_id, ts_ms, source, kind, symbol):
            return True
        else:
            self._duplicates_count += 1
            self._telemetry.emit("STATE_EVENT_DUPLICATE", {"id": event_id})
            return False
