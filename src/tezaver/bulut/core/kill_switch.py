# Tezaver Bulut - Kill Switch Service (P9)
"""
Emergency Kill Switch for mainnet safe shutdown.

3-level actions:
1. HALT: Stop new entries, disable autopilot
2. SAFE: Keep protective orders, monitoring continues
3. FLATTEN: Close all positions with reduceOnly market orders
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class KillSwitchState(Enum):
    """Kill switch states."""
    NORMAL = "NORMAL"       # Normal operations
    HALTED = "HALTED"       # No new entries, autopilot disabled
    SAFE = "SAFE"           # Halted + monitoring protected positions
    FLATTENING = "FLATTENING"  # Closing all positions
    FLAT = "FLAT"           # All positions closed


@dataclass
class KillSwitchEvent:
    """Kill switch event for audit log."""
    event_type: str
    from_state: str
    to_state: str
    reason: str
    actor: str
    timestamp: str
    positions_affected: int = 0


class KillSwitchService:
    """
    Emergency Kill Switch for safe shutdown.
    
    Provides idempotent operations:
    - halt(): Stop entries, disable autopilot
    - safe(): Keep protectives, monitor only
    - flatten(): Close all positions
    """
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._state = KillSwitchState.NORMAL
        self._reason: Optional[str] = None
        self._actor: Optional[str] = None
        self._changed_at: Optional[str] = None
        self._events: List[KillSwitchEvent] = []
        self._load_state()
    
    def _load_state(self):
        """Load kill switch state from persistence."""
        try:
            state = self._ctx.persistence.get_kill_switch_state()
            if state:
                self._state = KillSwitchState(state.get("state", "NORMAL"))
                self._reason = state.get("reason")
                self._actor = state.get("actor")
                self._changed_at = state.get("changed_at")
        except Exception:
            pass
    
    def _save_state(self):
        """Save kill switch state to persistence."""
        try:
            self._ctx.persistence.update_kill_switch_state({
                "state": self._state.value,
                "reason": self._reason,
                "actor": self._actor,
                "changed_at": self._changed_at
            })
        except Exception:
            pass
    
    def _log_event(
        self, 
        event_type: str, 
        from_state: str, 
        to_state: str,
        reason: str,
        actor: str,
        positions: int = 0
    ):
        """Log kill switch event."""
        event = KillSwitchEvent(
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            actor=actor,
            timestamp=datetime.now(timezone.utc).isoformat(),
            positions_affected=positions
        )
        self._events.append(event)
        if len(self._events) > 100:
            self._events = self._events[-50:]
        
        # Emit telemetry
        try:
            self._ctx.telemetry.emit({
                "event": f"KILL_SWITCH_{event_type}",
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
                "actor": actor
            })
        except Exception:
            pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current kill switch status."""
        return {
            "state": self._state.value,
            "reason": self._reason,
            "actor": self._actor,
            "changed_at": self._changed_at,
            "entries_allowed": self._state == KillSwitchState.NORMAL,
            "autopilot_allowed": self._state == KillSwitchState.NORMAL,
            "is_halted": self._state in [KillSwitchState.HALTED, KillSwitchState.SAFE, KillSwitchState.FLATTENING, KillSwitchState.FLAT],
            "events_count": len(self._events)
        }
    
    def check_entries_allowed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if new entries are allowed.
        
        Returns (allowed, reason_if_blocked).
        """
        if self._state == KillSwitchState.NORMAL:
            return True, None
        return False, f"KILL_SWITCH_{self._state.value}"
    
    def halt(self, reason: str, actor: str) -> Tuple[bool, str]:
        """
        HALT: Stop new entries, disable autopilot.
        
        Idempotent - safe to call multiple times.
        """
        if self._state == KillSwitchState.HALTED:
            return True, "Already halted"
        
        old_state = self._state.value
        self._state = KillSwitchState.HALTED
        self._reason = reason
        self._actor = actor
        self._changed_at = datetime.now(timezone.utc).isoformat()
        
        self._save_state()
        self._log_event("HALT", old_state, "HALTED", reason, actor)
        
        # Disable autopilot
        try:
            self._ctx.autopilot_service.disable(reason=f"kill_switch_halt: {reason}")
        except Exception:
            pass
        
        # Export incident if configured
        self._auto_export_incident(reason, actor, "HALT")
        
        return True, "Halted successfully"
    
    def safe(self, reason: str, actor: str) -> Tuple[bool, str]:
        """
        SAFE: Keep protective orders, monitor only.
        
        Like HALT but explicitly indicates protectives are maintained.
        """
        if self._state == KillSwitchState.SAFE:
            return True, "Already in safe mode"
        
        old_state = self._state.value
        self._state = KillSwitchState.SAFE
        self._reason = reason
        self._actor = actor
        self._changed_at = datetime.now(timezone.utc).isoformat()
        
        self._save_state()
        self._log_event("SAFE", old_state, "SAFE", reason, actor)
        
        # Disable autopilot
        try:
            self._ctx.autopilot_service.disable(reason=f"kill_switch_safe: {reason}")
        except Exception:
            pass
        
        return True, "Safe mode activated"
    
    def flatten(self, reason: str, actor: str) -> Tuple[bool, str, List[Dict]]:
        """
        FLATTEN: Close all positions with reduceOnly market orders.
        
        Returns (success, message, close_plans).
        """
        config = self._ctx.config
        mode = getattr(config, 'mode', 'REAL_TESTNET')
        
        # Safety check
        if mode not in ['REAL_MAINNET', 'REAL_TESTNET']:
            allow_testnet = getattr(config, 'allow_flatten_on_testnet', True)
            if not allow_testnet:
                return False, "FLATTEN not allowed in this mode", []
        
        old_state = self._state.value
        self._state = KillSwitchState.FLATTENING
        self._reason = reason
        self._actor = actor
        self._changed_at = datetime.now(timezone.utc).isoformat()
        
        self._save_state()
        
        # Get all open positions
        close_plans = self.get_flatten_plans()
        
        self._log_event("FLATTEN", old_state, "FLATTENING", reason, actor, len(close_plans))
        
        # Disable autopilot
        try:
            self._ctx.autopilot_service.disable(reason=f"kill_switch_flatten: {reason}")
        except Exception:
            pass
        
        # Export incident
        self._auto_export_incident(reason, actor, "FLATTEN")
        
        # Mark as FLAT if no positions
        if len(close_plans) == 0:
            self._state = KillSwitchState.FLAT
            self._save_state()
            return True, "No positions to flatten - now FLAT", []
        
        return True, f"Flatten initiated for {len(close_plans)} positions", close_plans
    
    def get_flatten_plans(self) -> List[Dict]:
        """
        Generate close plans for all open positions.
        
        Returns list of TradePlan-like dicts for reduceOnly closes.
        """
        plans = []
        
        try:
            positions = self._ctx.persistence.get_positions(status="OPEN")
            
            for pos in positions:
                symbol = pos.get("symbol", "")
                side = pos.get("side", "LONG")
                qty = pos.get("quantity", 0.0)
                
                if qty <= 0:
                    continue
                
                # Close side is opposite of position side
                close_side = "SELL" if side.upper() == "LONG" else "BUY"
                
                plans.append({
                    "plan_type": "CLOSE",
                    "symbol": symbol,
                    "side": close_side,
                    "quantity": qty,
                    "order_type": "MARKET",
                    "reduce_only": True,
                    "reason": "kill_switch_flatten",
                    "position_id": pos.get("position_id", "")
                })
        except Exception:
            pass
        
        return plans
    
    def resume(self, reason: str, actor: str) -> Tuple[bool, str]:
        """
        Resume normal operations.
        
        Only allowed from HALTED, SAFE, or FLAT states.
        """
        if self._state == KillSwitchState.NORMAL:
            return True, "Already in normal mode"
        
        if self._state == KillSwitchState.FLATTENING:
            return False, "Cannot resume while flattening - wait for completion"
        
        old_state = self._state.value
        self._state = KillSwitchState.NORMAL
        self._reason = reason
        self._actor = actor
        self._changed_at = datetime.now(timezone.utc).isoformat()
        
        self._save_state()
        self._log_event("RESUME", old_state, "NORMAL", reason, actor)
        
        return True, "Resumed normal operations"
    
    def _auto_export_incident(self, reason: str, actor: str, action: str):
        """Automatically export incident bundle if configured."""
        config = self._ctx.config
        if not getattr(config, 'kill_switch_auto_export_incident', True):
            return
        
        try:
            # Export incident bundle
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            bundle_path = f"data/incidents/kill_switch_{action.lower()}_{timestamp}.json"
            
            bundle = {
                "type": "kill_switch_incident",
                "action": action,
                "reason": reason,
                "actor": actor,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state_before": self._state.value,
                "open_positions": len(self._ctx.persistence.get_positions(status="OPEN") or []),
                "recent_events": [
                    {
                        "type": e.event_type,
                        "from": e.from_state,
                        "to": e.to_state,
                        "reason": e.reason,
                        "ts": e.timestamp
                    }
                    for e in self._events[-10:]
                ]
            }
            
            import json
            import os
            os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
            with open(bundle_path, 'w') as f:
                json.dump(bundle, f, indent=2)
        except Exception:
            pass
    
    def get_events(self, limit: int = 20) -> List[Dict]:
        """Get recent kill switch events."""
        events = self._events[-limit:]
        return [
            {
                "event_type": e.event_type,
                "from_state": e.from_state,
                "to_state": e.to_state,
                "reason": e.reason,
                "actor": e.actor,
                "timestamp": e.timestamp,
                "positions_affected": e.positions_affected
            }
            for e in reversed(events)
        ]
