"""
MX-3011: LiveReconciliation - Restart state reconciliation for LIVE mode.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ReconciliationResult:
    """Result of reconciliation check."""
    is_consistent: bool = True
    safe_mode_required: bool = False
    open_positions: List[Dict] = field(default_factory=list)
    open_orders: List[Dict] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "is_consistent": self.is_consistent,
            "safe_mode_required": self.safe_mode_required,
            "open_positions_count": len(self.open_positions),
            "open_orders_count": len(self.open_orders),
            "issues": self.issues
        }


class LiveReconciliation:
    """
    MX-3011: LiveReconciliation
    Checks state consistency on LIVE engine restart.
    """
    
    def __init__(self, state_path: str = "data/matrix/live_state.json"):
        self.state_path = Path(state_path)
        self.telemetry: List[Dict] = []
    
    def check(self, run_id: str) -> ReconciliationResult:
        """
        Check state consistency for restart.
        Returns ReconciliationResult with safe_mode flag if inconsistent.
        """
        self._emit_event("RECONCILE_STARTED", {"run_id": run_id})
        
        result = ReconciliationResult()
        
        # Load previous state
        state = self._load_state()
        
        if not state:
            # No previous state - clean start
            self._emit_event("RECONCILE_FINISHED", {
                "run_id": run_id,
                "result": "CLEAN_START"
            })
            return result
        
        # Check for open positions
        open_positions = state.get("open_positions", [])
        if open_positions:
            result.open_positions = open_positions
            result.issues.append(f"Found {len(open_positions)} open positions from previous run")
            result.is_consistent = False
            result.safe_mode_required = True
        
        # Check for open orders
        open_orders = state.get("open_orders", [])
        if open_orders:
            result.open_orders = open_orders
            result.issues.append(f"Found {len(open_orders)} open orders from previous run")
            result.is_consistent = False
            result.safe_mode_required = True
        
        # Check for run mismatch
        last_run_id = state.get("run_id")
        if last_run_id and last_run_id != run_id:
            result.issues.append(f"Run ID mismatch: state has {last_run_id}, current is {run_id}")
        
        if result.is_consistent:
            self._emit_event("RECONCILE_FINISHED", {
                "run_id": run_id,
                "result": "CONSISTENT"
            })
        else:
            self._emit_event("RECONCILE_ERROR", {
                "run_id": run_id,
                "result": "INCONSISTENT",
                "issues": result.issues,
                "safe_mode": result.safe_mode_required
            })
        
        return result
    
    def save_state(self, run_id: str, open_positions: List[Dict] = None, open_orders: List[Dict] = None):
        """Save current state for future reconciliation."""
        state = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "open_positions": open_positions or [],
            "open_orders": open_orders or []
        }
        
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2)
    
    def clear_state(self):
        """Clear state file (on clean shutdown)."""
        if self.state_path.exists():
            self.state_path.unlink()
    
    def _load_state(self) -> Optional[Dict]:
        """Load state from file."""
        if not self.state_path.exists():
            return None
        try:
            with open(self.state_path, "r") as f:
                return json.load(f)
        except:
            return None
    
    def _emit_event(self, kind: str, data: Dict):
        """Emit telemetry event."""
        event = {
            "ts": datetime.now().isoformat(),
            "kind": kind,
            **data
        }
        self.telemetry.append(event)
    
    def get_telemetry(self) -> List[Dict]:
        """Get accumulated telemetry events."""
        return self.telemetry
