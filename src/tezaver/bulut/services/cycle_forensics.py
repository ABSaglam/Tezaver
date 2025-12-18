# Tezaver Bulut - Cycle Forensics Service
"""
Collects and persists a timeline for each 15m cycle.
Used for "One-Click Debug" and incident bundles.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.schemas.cycle_timeline_v1 import CycleTimelineV1, CycleStageV1

class CycleForensicsService:
    """
    Aggregates state from Scheduler, Scanner, Decider, and Executor
    into a deterministic timeline object for the cycle.
    """
    
    def __init__(self):
        pass
        
    def collect_and_save(
        self,
        ctx: BulutContext,
        cycle_index: int,
        cycle_ts: datetime,
        sched_stats: Dict[str, Any],
        scan_stats: Dict[str, Any],
        decider_stats: Dict[str, Any],
        exec_stats: Dict[str, Any],
        risk_stats: Dict[str, Any]
    ) -> CycleTimelineV1:
        """
        Builds the timeline and persists it.
        """
        timeline = CycleTimelineV1(
            cycle_index=cycle_index,
            cycle_ts=cycle_ts
        )
        
        # 1. SCHED Stage
        # sched_stats input: { "planned_n": 3, "priority_n": 0, "rr_n": 3, "missed_n": 0 }
        timeline.stages.append(CycleStageV1(
            name="SCHED",
            status="WARN" if sched_stats.get("missed_n", 0) > 0 else "OK",
            details=sched_stats
        ))
        
        # 2. DATA Stage (part of Sched/Poller)
        # We might not have granular data stats passed yet, but let's assume sched_stats has it or separate
        # distinct "DATA" stage if poller provided ingestion details.
        # For now, merge with SCHED or add placeholder.
        # Let's add explicit DATA stage if scan_stats has universe count
        timeline.stages.append(CycleStageV1(
            name="DATA",
            status="OK",
            details={
                "universe_size": sched_stats.get("universe_n", 0),
                "ingested": sched_stats.get("scanned_n", 0)
            }
        ))
        
        # 3. SCAN Stage
        # scan_stats: { "candidates_count": 10, "top_score": 85, "pattern_count": 5 }
        timeline.stages.append(CycleStageV1(
            name="SCAN",
            status="OK",
            details=scan_stats
        ))
        
        # 4. DECIDE Stage
        # decider_stats: { "plans_count": 2, "blocked_count": 1 }
        timeline.stages.append(CycleStageV1(
            name="DECIDE",
            status="OK",
            details=decider_stats
        ))
        
        # 5. EXEC Stage
        # exec_stats: { "executed": 1, "failed": 0 }
        timeline.stages.append(CycleStageV1(
            name="EXEC",
            status="ERR" if exec_stats.get("failed", 0) > 0 else "OK",
            details=exec_stats
        ))
        
        # 6. RISK Stage
        # risk_stats: { "halted": False, "daily_pnl": 123.4 }
        status_risk = "ERR" if risk_stats.get("halted") else "OK"
        timeline.stages.append(CycleStageV1(
            name="RISK",
            status=status_risk,
            details=risk_stats
        ))
        
        # Persist
        json_str = json.dumps(timeline.to_dict())
        ctx.persistence.upsert_cycle_timeline(cycle_index, cycle_ts, json_str)
        
        # Emit Telemetry
        ctx.telemetry.emit("CYCLE_TIMELINE_SAVED", {
            "cycle_index": cycle_index,
            "stages": [s.name for s in timeline.stages],
            "risk_halted": risk_stats.get("halted", False)
        })
        
        return timeline
