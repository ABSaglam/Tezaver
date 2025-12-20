"""
Cycle Events - V4 Compatible Shim

Provides cycle record parsing and incident bundle building.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path

class CycleAlertLevel(Enum):
    OK = "OK"
    WARN = "WARN"
    BLOCK = "BLOCK"

@dataclass
class CycleRecord:
    """Represents a trade cycle record."""
    cycle_idx: int
    status: str
    alert_level: CycleAlertLevel = CycleAlertLevel.OK
    open_order_id: Optional[str] = None
    close_order_id: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    net_pnl: Optional[float] = None
    gross_pnl: Optional[float] = None
    fee: Optional[float] = None
    cycle_bars: int = 0
    eff_lag: Optional[float] = None
    residual_after: Optional[float] = None
    reduce_only: bool = False
    pos_after: Optional[float] = None
    start_ts: Optional[str] = None
    done_ts: Optional[str] = None

@dataclass
class IncidentBundleSpec:
    """Specification for incident bundle creation."""
    symbol: str
    timeframe: str
    cycle_idx: int
    ndjson_path: str
    equity_start: float = 100.0
    out_dir: str = "data/incidents"
    only_relevant: bool = True

TIMELINE_EVENT_TYPES = [
    "CYCLE_START",
    "CYCLE_DONE",
    "ORDER_PLACED",
    "ORDER_FILLED",
    "PREFLIGHT_EVAL",
    "RISK_LIMIT_EVAL",
]

def load_cycle_records(
    ndjson_path: Path,
    symbol: str,
    timeframe: str,
    last_n: int = 10,
) -> List[CycleRecord]:
    return []

def compute_aggregates(records: List[CycleRecord]) -> Dict[str, Any]:
    ok_count = sum(1 for r in records if r.alert_level == CycleAlertLevel.OK)
    warn_count = sum(1 for r in records if r.alert_level == CycleAlertLevel.WARN)
    block_count = sum(1 for r in records if r.alert_level == CycleAlertLevel.BLOCK)
    
    return {
        "ok_count": ok_count,
        "warn_count": warn_count,
        "block_count": block_count,
        "total": len(records),
    }

def get_cycle_events(
    ndjson_path: Path,
    cycle_idx: int,
    symbol: str,
) -> List[Dict[str, Any]]:
    return []

def build_incident_bundle(spec: IncidentBundleSpec) -> Dict[str, Any]:
    return {
        "success": False,
        "error": "Stub implementation",
        "bundle_path": None,
        "files": [],
        "alert": "OK",
    }
