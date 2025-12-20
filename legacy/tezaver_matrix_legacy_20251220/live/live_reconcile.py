"""
Restart Reconciliation Service for Matrix Live.

Ensures state consistency after restart:
- Loads persisted position/order state
- Reconciles with exchange (REAL modes)
- Detects residual positions/orders
- Emits RECON_* telemetry events
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json


@dataclass
class CellRecon:
    """Reconciliation result for a single cell."""
    cell_id: str
    symbol: str
    timeframe: str
    profile_id: str
    
    # Position reconcile
    pos_amt_exchange: float = 0.0
    pos_state_local_before: str = "UNKNOWN"
    pos_state_local_after: str = "UNKNOWN"
    
    # Open orders reconcile
    open_orders_supported: bool = False
    open_orders_count_exchange: int = 0
    
    # Actions taken
    actions_taken: List[str] = field(default_factory=list)
    
    # Status
    ok: bool = True
    warnings: List[str] = field(default_factory=list)
    paused: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "profile_id": self.profile_id,
            "pos_amt_exchange": round(self.pos_amt_exchange, 8),
            "pos_state_local_before": self.pos_state_local_before,
            "pos_state_local_after": self.pos_state_local_after,
            "open_orders_supported": self.open_orders_supported,
            "open_orders_count_exchange": self.open_orders_count_exchange,
            "actions_taken": self.actions_taken,
            "ok": self.ok,
            "warnings": self.warnings,
            "paused": self.paused,
        }


@dataclass
class ReconcileResult:
    """Overall reconciliation result."""
    per_cell: List[CellRecon] = field(default_factory=list)
    ok: bool = True
    warnings: List[str] = field(default_factory=list)
    exchange_mode: str = "UNKNOWN"
    paused_cells: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "per_cell": [c.to_dict() for c in self.per_cell],
            "ok": self.ok,
            "warnings": self.warnings,
            "exchange_mode": self.exchange_mode,
            "cell_count": len(self.per_cell),
            "paused_cells": self.paused_cells,
        }


class ReconcileService:
    """
    Restart reconciliation service.
    
    Loads persisted state, reconciles with exchange, emits telemetry.
    """
    
    STATE_DIR = "data/state"
    FINGERPRINTS_FILE = "fingerprints.json"
    POSITIONS_FILE = "positions.json"
    
    def __init__(
        self,
        gateway=None,
        position_store=None,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        exchange_mode: str = "DRY_RUN",
        armed: bool = False,
        exchange_enabled: bool = False,
        residual_action: str = "PAUSE_CELL",  # PAUSE_CELL / WARN_ONLY
    ):
        self._gateway = gateway
        self._position_store = position_store
        self._event_sink = event_sink
        self._exchange_mode = exchange_mode
        self._armed = armed
        self._exchange_enabled = exchange_enabled
        self._residual_action = residual_action
        
        # Last result for UI
        self._last_result: Optional[ReconcileResult] = None
        
        # Paused cells set
        self._paused_cells: set = set()
    
    @property
    def last_result(self) -> Optional[ReconcileResult]:
        return self._last_result
    
    @property
    def paused_cells(self) -> set:
        return self._paused_cells.copy()
    
    def is_cell_paused(self, cell_id: str) -> bool:
        return cell_id in self._paused_cells
    
    def _emit(self, event: Dict[str, Any]) -> None:
        """Emit telemetry event with mandatory fields."""
        if self._event_sink:
            event.setdefault("ts", datetime.now(timezone.utc).isoformat())
            event.setdefault("exchange_mode", self._exchange_mode)
            event.setdefault("armed", self._armed)
            event.setdefault("exchange_enabled", self._exchange_enabled)
            self._event_sink(event)
    
    def _emit_cell(self, event_type: str, cell_id: str, symbol: str, tf: str, 
                   profile_id: str, details: Dict[str, Any]) -> None:
        """Emit cell-scoped event with all mandatory fields."""
        self._emit({
            "event_type": event_type,
            "symbol": symbol,
            "timeframe": tf,
            "cell_id": cell_id,
            "profile_id": profile_id,
            "details": details,
        })
    
    def load_persisted_state(self) -> Dict[str, Any]:
        """Load persisted state from disk."""
        state_dir = Path(self.STATE_DIR)
        loaded = {
            "fingerprints_loaded": 0,
            "positions_loaded": 0,
            "errors": [],
        }
        
        # Load fingerprints into gateway
        fp_path = state_dir / self.FINGERPRINTS_FILE
        if fp_path.exists() and self._gateway:
            try:
                if hasattr(self._gateway, 'load_fingerprints'):
                    self._gateway.load_fingerprints(str(fp_path))
                    fps = self._gateway.get_fingerprints() if hasattr(self._gateway, 'get_fingerprints') else {}
                    loaded["fingerprints_loaded"] = len(fps)
            except Exception as e:
                loaded["errors"].append(f"fingerprints: {e}")
        
        # Load positions into store
        pos_path = state_dir / self.POSITIONS_FILE
        if pos_path.exists() and self._position_store:
            try:
                with open(pos_path, "r") as f:
                    positions_data = json.load(f)
                if hasattr(self._position_store, '_positions'):
                    from tezaver.matrix.live.strategy_signal import CellPosition, PositionState
                    for key, data in positions_data.items():
                        pos = CellPosition(
                            state=PositionState(data.get("state", "FLAT")),
                            open_order_id=data.get("open_order_id"),
                            close_order_id=data.get("close_order_id"),
                            qty=data.get("qty", 0.0),
                            last_fingerprint=data.get("last_fingerprint"),
                        )
                        self._position_store._positions[key] = pos
                    loaded["positions_loaded"] = len(positions_data)
            except Exception as e:
                loaded["errors"].append(f"positions: {e}")
        
        return loaded
    
    def save_persisted_state(self) -> Dict[str, Any]:
        """Save state to disk for restart durability."""
        state_dir = Path(self.STATE_DIR)
        state_dir.mkdir(parents=True, exist_ok=True)
        saved = {
            "fingerprints_saved": 0,
            "positions_saved": 0,
            "errors": [],
        }
        
        # Save fingerprints
        if self._gateway and hasattr(self._gateway, 'save_fingerprints'):
            try:
                fp_path = state_dir / self.FINGERPRINTS_FILE
                self._gateway.save_fingerprints(str(fp_path))
                fps = self._gateway.get_fingerprints() if hasattr(self._gateway, 'get_fingerprints') else {}
                saved["fingerprints_saved"] = len(fps)
            except Exception as e:
                saved["errors"].append(f"fingerprints: {e}")
        
        # Save positions
        if self._position_store and hasattr(self._position_store, '_positions'):
            try:
                pos_path = state_dir / self.POSITIONS_FILE
                positions_data = {}
                for key, pos in self._position_store._positions.items():
                    positions_data[key] = {
                        "state": pos.state.value if hasattr(pos.state, 'value') else str(pos.state),
                        "open_order_id": pos.open_order_id,
                        "close_order_id": pos.close_order_id,
                        "qty": pos.qty,
                        "last_fingerprint": pos.last_fingerprint,
                    }
                with open(pos_path, "w") as f:
                    json.dump(positions_data, f, indent=2)
                saved["positions_saved"] = len(positions_data)
            except Exception as e:
                saved["errors"].append(f"positions: {e}")
        
        return saved
    
    def reconcile_cells(self, cells: List[Dict[str, str]]) -> ReconcileResult:
        """Reconcile list of cells."""
        result = ReconcileResult(exchange_mode=self._exchange_mode)
        
        # Emit start with mandatory fields
        self._emit({
            "event_type": "RECON_START",
            "cell_count": len(cells),
            "cells": [c.get("symbol", "") for c in cells],
            "details": {
                "residual_action": self._residual_action,
                "symbols": [c.get("symbol", "") for c in cells],
                "timeframes": [c.get("timeframe", "") for c in cells],
            },
        })
        
        for cell in cells:
            cell_recon = self.reconcile_one(cell)
            result.per_cell.append(cell_recon)
            
            if not cell_recon.ok:
                result.ok = False
            if cell_recon.warnings:
                result.warnings.extend(cell_recon.warnings)
            if cell_recon.paused:
                result.paused_cells.append(cell_recon.cell_id)
        
        # Emit done
        self._emit({
            "event_type": "RECON_DONE",
            "ok": result.ok,
            "warnings": result.warnings,
            "cell_count": len(result.per_cell),
            "cells_with_warnings": sum(1 for c in result.per_cell if c.warnings),
            "paused_cells": result.paused_cells,
            "details": {
                "paused_count": len(result.paused_cells),
                "ok_count": sum(1 for c in result.per_cell if c.ok),
            },
        })
        
        self._last_result = result
        return result
    
    def reconcile_one(self, cell: Dict[str, str]) -> CellRecon:
        """Reconcile a single cell."""
        symbol = cell.get("symbol", "")
        tf = cell.get("timeframe", "")
        profile_id = cell.get("profile_id", "default")
        cell_id = f"{symbol}|{tf}|{profile_id}"
        
        recon = CellRecon(
            cell_id=cell_id,
            symbol=symbol,
            timeframe=tf,
            profile_id=profile_id,
        )
        
        # Get local state before reconcile
        if self._position_store:
            pos = self._position_store.get(symbol, tf, profile_id)
            recon.pos_state_local_before = pos.state.value if hasattr(pos.state, 'value') else str(pos.state)
        
        # Exchange reconcile (REAL modes only)
        if self._exchange_mode.startswith("REAL") and self._gateway:
            self._reconcile_exchange(recon, symbol, tf, profile_id, cell_id)
        else:
            # DRY_RUN / DUMMY_ORDER - no exchange reconcile, emit minimal events
            recon.actions_taken.append("LOCAL_ONLY")
            
            # Emit RECON_POSITION with LOCAL_ONLY action
            self._emit_cell("RECON_POSITION", cell_id, symbol, tf, profile_id, {
                "pos_amt_exchange": 0.0,
                "pos_state_local_before": recon.pos_state_local_before,
                "pos_state_local_after": recon.pos_state_local_before,  # unchanged
                "action_taken": "LOCAL_ONLY",
                "warning": None,
            })
            
            # Emit RECON_OPEN_ORDERS with NOT_SUPPORTED
            self._emit_cell("RECON_OPEN_ORDERS", cell_id, symbol, tf, profile_id, {
                "supported": False,
                "open_orders_count_exchange": 0,
                "reason": "NOT_SUPPORTED_DRY_MODE",
            })
        
        # Get local state after reconcile
        if self._position_store:
            pos = self._position_store.get(symbol, tf, profile_id)
            recon.pos_state_local_after = pos.state.value if hasattr(pos.state, 'value') else str(pos.state)
        
        # Check for warnings and emit RECON_WARN
        if recon.warnings:
            recon.ok = False
            severity = "WARN"
            suggested_actions = []
            
            # Determine severity and actions
            if recon.paused:
                severity = "BLOCK"
                suggested_actions.append("UNPAUSE_CELL_AFTER_MANUAL_CHECK")
            elif "EXCHANGE_POS_NONZERO" in str(recon.warnings):
                suggested_actions.append("CHECK_EXCHANGE_POSITION")
            
            self._emit_cell("RECON_WARN", cell_id, symbol, tf, profile_id, {
                "warnings": recon.warnings,
                "severity": severity,
                "suggested_actions": suggested_actions,
                "paused": recon.paused,
            })
        
        return recon
    
    def _reconcile_exchange(self, recon: CellRecon, symbol: str, tf: str, 
                            profile_id: str, cell_id: str) -> None:
        """Reconcile with exchange for REAL modes."""
        try:
            # Get position from exchange
            if hasattr(self._gateway, 'get_position_snapshot'):
                pos_snap = self._gateway.get_position_snapshot(symbol)
                if pos_snap and isinstance(pos_snap, dict):
                    recon.pos_amt_exchange = float(pos_snap.get("positionAmt", 0.0))
                    
                    action_taken = "NONE"
                    warning = None
                    
                    # Reconcile: if exchange has position, set local to LONG
                    if recon.pos_amt_exchange > 0 and self._position_store:
                        pos = self._position_store.get(symbol, tf, profile_id)
                        if pos.state.value != "LONG":
                            pos.state = pos.state.__class__("LONG")
                            pos.qty = recon.pos_amt_exchange
                            action_taken = "SET_LONG"
                            warning = "EXCHANGE_POS_NONZERO_LOCAL_FLAT"
                            recon.actions_taken.append("SET_LONG")
                            recon.warnings.append(f"Exchange has {recon.pos_amt_exchange} but local was FLAT")
                            
                            # Apply safety action
                            if self._residual_action == "PAUSE_CELL":
                                self._paused_cells.add(cell_id)
                                recon.paused = True
                                recon.actions_taken.append("PAUSE_CELL")
                        else:
                            action_taken = "CONFIRM_LONG"
                            
                    elif recon.pos_amt_exchange == 0 and self._position_store:
                        pos = self._position_store.get(symbol, tf, profile_id)
                        if pos.state.value == "LONG":
                            pos.state = pos.state.__class__("FLAT")
                            pos.qty = 0.0
                            action_taken = "RESET_FLAT"
                            warning = "LOCAL_LONG_BUT_EXCHANGE_FLAT"
                            recon.actions_taken.append("RESET_FLAT")
                            recon.warnings.append("Local was LONG but exchange has no position")
                        else:
                            action_taken = "CONFIRM_FLAT"
                    
                    # Emit RECON_POSITION
                    self._emit_cell("RECON_POSITION", cell_id, symbol, tf, profile_id, {
                        "pos_amt_exchange": recon.pos_amt_exchange,
                        "pos_state_local_before": recon.pos_state_local_before,
                        "pos_state_local_after": "LONG" if recon.pos_amt_exchange > 0 else "FLAT",
                        "action_taken": action_taken,
                        "warning": warning,
                    })
            
            # Check open orders
            self._reconcile_open_orders(recon, symbol, tf, profile_id, cell_id)
                    
        except Exception as e:
            recon.ok = False
            recon.warnings.append(f"Exchange error: {e}")
            
            # Emit error position event
            self._emit_cell("RECON_POSITION", cell_id, symbol, tf, profile_id, {
                "pos_amt_exchange": 0.0,
                "pos_state_local_before": recon.pos_state_local_before,
                "pos_state_local_after": recon.pos_state_local_before,
                "action_taken": "ERROR",
                "warning": f"EXCHANGE_ERROR: {e}",
            })
    
    def _reconcile_open_orders(self, recon: CellRecon, symbol: str, tf: str,
                               profile_id: str, cell_id: str) -> None:
        """Check open orders on exchange."""
        if hasattr(self._gateway, 'get_open_orders'):
            recon.open_orders_supported = True
            try:
                open_orders = self._gateway.get_open_orders(symbol)
                recon.open_orders_count_exchange = len(open_orders) if open_orders else 0
                
                self._emit_cell("RECON_OPEN_ORDERS", cell_id, symbol, tf, profile_id, {
                    "supported": True,
                    "open_orders_count_exchange": recon.open_orders_count_exchange,
                    "reason": None,
                })
                
                if recon.open_orders_count_exchange > 0:
                    recon.warnings.append(f"Exchange has {recon.open_orders_count_exchange} open orders")
                    
                    # Apply safety action for open orders
                    if self._residual_action == "PAUSE_CELL":
                        self._paused_cells.add(cell_id)
                        recon.paused = True
                        recon.actions_taken.append("PAUSE_CELL_OPEN_ORDERS")
                        
            except Exception as e:
                recon.open_orders_supported = False
                self._emit_cell("RECON_OPEN_ORDERS", cell_id, symbol, tf, profile_id, {
                    "supported": False,
                    "open_orders_count_exchange": 0,
                    "reason": f"ERROR: {e}",
                })
        else:
            recon.open_orders_supported = False
            self._emit_cell("RECON_OPEN_ORDERS", cell_id, symbol, tf, profile_id, {
                "supported": False,
                "open_orders_count_exchange": 0,
                "reason": "NOT_SUPPORTED",
            })
