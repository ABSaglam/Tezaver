"""
Order State Store

Per-cell tracking of last ORDER_SUBMIT/ORDER_RESULT/ORDER_BLOCKED events.
Used by Live Ops Console for per-cell order display.
"""

from typing import Dict, Any, Optional
from datetime import datetime


class OrderStateStore:
    """
    Per-cell order state tracking.
    
    Key format: "{symbol}|{timeframe}|{profile_id}"
    """
    
    def __init__(self):
        self._cells: Dict[str, Dict[str, Any]] = {}
    
    def _get_cell_key(self, event: Dict[str, Any]) -> Optional[str]:
        """Get cell key from event."""
        symbol = event.get("symbol")
        timeframe = event.get("timeframe")
        profile_id = event.get("profile_id")
        
        if not symbol or not timeframe:
            return None
        
        return f"{symbol}|{timeframe}|{profile_id or 'unknown'}"
    
    def apply_event(self, event: Dict[str, Any]) -> None:
        """
        Apply an event to update cell state.
        
        Handles: ORDER_SUBMIT, ORDER_RESULT, ORDER_BLOCKED, ROUTER_CLUSTER_GUARDRAIL
        """
        event_type = event.get("event_type", "")
        cell_key = self._get_cell_key(event)
        
        if not cell_key:
            return
        
        # Initialize cell if needed
        if cell_key not in self._cells:
            self._cells[cell_key] = {
                "symbol": event.get("symbol"),
                "timeframe": event.get("timeframe"),
                "profile_id": event.get("profile_id"),
                "last_submit_ts": None,
                "last_result_ts": None,
                "last_blocked_ts": None,
                "last_order_id": None,
                "last_exec_mode": None,
                "last_exchange_mode": None,
                "last_success": None,
                "last_duplicate": None,
                "last_paused": None,
                "last_reason": None,
                "last_fingerprint": None,
                "last_allow": None,
            }
        
        cell = self._cells[cell_key]
        ts = event.get("ts", datetime.now().isoformat())
        
        if event_type == "ORDER_SUBMIT":
            cell["last_submit_ts"] = ts
            cell["last_order_id"] = event.get("order_id")
            cell["last_exec_mode"] = event.get("exec_mode")
            cell["last_exchange_mode"] = event.get("exchange_mode")
            cell["last_fingerprint"] = event.get("fingerprint")
        
        elif event_type == "ORDER_RESULT":
            cell["last_result_ts"] = ts
            cell["last_success"] = event.get("success")
            cell["last_duplicate"] = event.get("duplicate")
            cell["last_paused"] = event.get("paused")
            cell["last_reason"] = event.get("reason")
            cell["last_order_id"] = event.get("order_id")
            cell["last_exec_mode"] = event.get("exec_mode")
            cell["last_fingerprint"] = event.get("fingerprint")
        
        elif event_type == "ORDER_BLOCKED":
            cell["last_blocked_ts"] = ts
            cell["last_reason"] = event.get("reason")
            cell["last_allow"] = False
        
        elif event_type == "ROUTER_CLUSTER_GUARDRAIL":
            cell["last_allow"] = event.get("allow")
    
    def get_cell_state(self, cell_key: str) -> Optional[Dict[str, Any]]:
        """Get state for a specific cell."""
        return self._cells.get(cell_key)
    
    def get_all_cells(self) -> Dict[str, Dict[str, Any]]:
        """Get all cell states."""
        return dict(self._cells)
    
    def get_cells_list(self) -> list:
        """Get cells as a list for UI table display."""
        rows = []
        for key, cell in self._cells.items():
            fingerprint = cell.get("last_fingerprint", "")
            fingerprint_short = fingerprint[-25:] if fingerprint and len(fingerprint) > 25 else fingerprint
            
            rows.append({
                "cell_key": key,
                "symbol": cell.get("symbol"),
                "tf": cell.get("timeframe"),
                "profile_id": cell.get("profile_id"),
                "allow": "✅" if cell.get("last_allow") else ("❌" if cell.get("last_allow") is False else "-"),
                "exec_mode": cell.get("last_exec_mode", "-"),
                "order_id": cell.get("last_order_id", "-"),
                "last_submit": cell.get("last_submit_ts", "-")[:19] if cell.get("last_submit_ts") else "-",
                "last_result": cell.get("last_result_ts", "-")[:19] if cell.get("last_result_ts") else "-",
                "success": "✅" if cell.get("last_success") else ("❌" if cell.get("last_success") is False else "-"),
                "reason": cell.get("last_reason", "-"),
                "fingerprint": fingerprint_short or "-",
            })
        
        return rows
    
    def clear(self) -> None:
        """Clear all state."""
        self._cells.clear()
    
    def clear_cell(self, cell_key: str) -> None:
        """Clear state for a specific cell."""
        if cell_key in self._cells:
            del self._cells[cell_key]


# Global singleton instance
_order_state_store: Optional[OrderStateStore] = None


def get_order_state_store() -> OrderStateStore:
    """Get or create the global order state store."""
    global _order_state_store
    if _order_state_store is None:
        _order_state_store = OrderStateStore()
    return _order_state_store
