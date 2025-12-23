"""
Portfolio Provider V2
=====================

Real/SIM bridge for portfolio snapshots.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, data: Dict[str, Any]):
    """Write JSON safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

@dataclass
class PortfolioSnapshotV2:
    """Portfolio snapshot v2."""
    run_id: str
    stage: str
    built_ts_iso: str
    max_open_positions: int
    open_now: int
    capacity: int
    open_positions: List[Dict[str, Any]]
    open_orders: List[Dict[str, Any]]
    source: str  # "SIM_STATE"|"EMPTY"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "built_ts_iso": self.built_ts_iso,
            "max_open_positions": self.max_open_positions,
            "open_now": self.open_now,
            "capacity": self.capacity,
            "open_positions": self.open_positions,
            "open_orders": self.open_orders,
            "source": self.source
        }

class PortfolioProviderV2:
    """
    Portfolio provider with SIM/EMPTY modes.
    
    Modes:
    - SIM_STATE: Reads from SIM state file
    - EMPTY: Returns empty (backward compatible)
    """
    
    def __init__(self, mode: str = "EMPTY", home_dir: str = None):
        self.mode = mode
        self.home_dir = home_dir
    
    def get_snapshot(
        self,
        stage: str,
        run_id: str,
        max_open_positions: int = 20
    ) -> PortfolioSnapshotV2:
        """
        Get portfolio snapshot.
        
        Args:
            stage: Run stage
            run_id: Run ID
            max_open_positions: Max positions limit
            
        Returns:
            PortfolioSnapshotV2
        """
        if self.mode == "SIM_STATE":
            return self._get_sim_snapshot(stage, run_id, max_open_positions)
        else:
            return self._get_empty_snapshot(stage, run_id, max_open_positions)
    
    def _get_sim_snapshot(
        self,
        stage: str,
        run_id: str,
        max_open_positions: int
    ) -> PortfolioSnapshotV2:
        """Get snapshot from SIM state v2."""
        from tezaver.matrix.pool.portfolio_state_store_sim_v1 import load_state_v2
        
        state_v2 = load_state_v2(stage, run_id, self.home_dir)
        open_positions = [p.to_dict() for p in state_v2.positions if p.status == "OPEN"]
        open_now = len(open_positions)
        capacity = max(0, max_open_positions - open_now)
        
        return PortfolioSnapshotV2(
            run_id=run_id,
            stage=stage,
            built_ts_iso=now_iso(),
            max_open_positions=max_open_positions,
            open_now=open_now,
            capacity=capacity,
            open_positions=open_positions,
            open_orders=[],
            source="SIM_STATE"
        )
    
    def _get_empty_snapshot(
        self,
        stage: str,
        run_id: str,
        max_open_positions: int
    ) -> PortfolioSnapshotV2:
        """Get empty snapshot (backward compatible)."""
        return PortfolioSnapshotV2(
            run_id=run_id,
            stage=stage,
            built_ts_iso=now_iso(),
            max_open_positions=max_open_positions,
            open_now=0,
            capacity=max_open_positions,
            open_positions=[],
            open_orders=[],
            source="EMPTY"
        )
    
    def write_snapshot_report(
        self,
        snapshot: PortfolioSnapshotV2,
        reports_dir: Path
    ) -> str:
        """Write snapshot to report file."""
        path = reports_dir / "pool_portfolio_snapshot_v2.json"
        write_json(path, snapshot.to_dict())
        return str(path)
