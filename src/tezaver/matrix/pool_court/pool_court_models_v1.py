"""
Pool Court Models V1
====================

Data models for the Pool Court system (Jury/Judge).
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class PoolProsecutorNoteV1:
    """Prosecutor's thesis (placeholder for future AI integration)."""
    theses: List[str] = field(default_factory=list)

@dataclass
class PoolDefenseNoteV1:
    """Defense attacks (placeholder for future AI integration)."""
    attacks: List[str] = field(default_factory=list)

@dataclass
class PoolJuryScorecardV1:
    """Jury's scorecard built from evidence."""
    run_id: str
    stage: str
    engine_version: str
    data_fingerprint: str
    config_signature: str
    built_ts_iso: str
    evidence_ok: bool
    universe_cells: int
    intents_created: int
    selected_count: int
    allowed_count: int
    blocked_count: int
    planned_orders: int
    planned_total_notional: float
    restart_reconcile_verdict: str  # "OK"|"NEEDS_SAFE_MODE"|"UNKNOWN"
    kill_switch_triggered: bool  # Phase 5B.1
    key_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "engine_version": self.engine_version,
            "data_fingerprint": self.data_fingerprint,
            "config_signature": self.config_signature,
            "built_ts_iso": self.built_ts_iso,
            "evidence_ok": self.evidence_ok,
            "universe_cells": self.universe_cells,
            "intents_created": self.intents_created,
            "selected_count": self.selected_count,
            "allowed_count": self.allowed_count,
            "blocked_count": self.blocked_count,
            "planned_orders": self.planned_orders,
            "planned_total_notional": self.planned_total_notional,
            "restart_reconcile_verdict": self.restart_reconcile_verdict,
            "kill_switch_triggered": self.kill_switch_triggered,
            "key_notes": self.key_notes
        }

@dataclass
class PoolGateResultV1:
    """Result of a single gate evaluation."""
    gate_id: str
    status: str  # "PASS"|"FAIL"|"WARN"|"IMPROVE"
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "reason": self.reason
        }

@dataclass
class PoolCourtVerdictV1:
    """Final court verdict."""
    run_id: str
    stage: str
    engine_version: str
    data_fingerprint: str
    config_signature: str
    built_ts_iso: str
    verdict: str  # "PASS"|"IMPROVE"|"FAIL"
    gates: List[PoolGateResultV1]
    summary: str
    suggested_actions: List[str]
    evidence_paths: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "engine_version": self.engine_version,
            "data_fingerprint": self.data_fingerprint,
            "config_signature": self.config_signature,
            "built_ts_iso": self.built_ts_iso,
            "verdict": self.verdict,
            "gates": [g.to_dict() for g in self.gates],
            "summary": self.summary,
            "suggested_actions": self.suggested_actions,
            "evidence_paths": self.evidence_paths
        }
