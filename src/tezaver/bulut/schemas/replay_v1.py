# Tezaver Bulut - Replay Bundle Schema V1
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ReplayBarV1:
    ts: int  # ms
    o: float
    h: float
    l: float
    c: float
    v: float
    
    def to_dict(self):
        return {"ts": self.ts, "o": self.o, "h": self.h, "l": self.l, "c": self.c, "v": self.v}

@dataclass
class ReplayBundleV1:
    bundle_id: str
    cycle_ts: str # ISO
    created_ts: str # ISO
    
    # Inputs
    universe: List[str]
    bars_snapshot: Dict[str, Dict[str, List[dict]]] # symbol -> tf -> [bars]
    policy_state: Dict[str, dict] # symbol -> policy state
    active_config_hash: str
    active_config_json: str
    risk_state_json: str # Snapshot of limits/usage
    
    # Expected Outputs (for verification)
    expected_decision_ids: Dict[str, str] # symbol -> decision_id
    expected_plans: Dict[str, dict] # symbol -> plan_json
    
    notes: str = ""
    
    def to_dict(self):
        return {
            "bundle_id": self.bundle_id,
            "cycle_ts": self.cycle_ts,
            "created_ts": self.created_ts,
            "universe": self.universe,
            "bars_snapshot": self.bars_snapshot,
            "policy_state": self.policy_state,
            "active_config_hash": self.active_config_hash,
            "active_config_json": self.active_config_json,
            "risk_state_json": self.risk_state_json,
            "expected_decision_ids": self.expected_decision_ids,
            "expected_plans": self.expected_plans,
            "notes": self.notes
        }

@dataclass
class ReplayResultV1:
    run_id: str
    bundle_id: str
    status: str # MATCH / DRIFT / ERROR
    executed_ts: str
    
    drift_details: Dict[str, Any] # Differences found
    logs: List[str]
