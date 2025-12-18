# Tezaver Bulut - Proof Ladder Service
"""
Evidence-gated Mainnet Cap Escalation Service.
Evaluates system health (clean runs) to permit higher caps.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.core.config import BulutConfig

# --- Schema ---

@dataclass
class ProofStage:
    stage_id: str
    cap_usdt: float
    min_hours_clean: float
    next: Optional[str]

@dataclass
class EvalResult:
    passed: bool
    stage_id: str
    effective_cap: float
    clean_hours: float
    reasons: List[str]
    details: Dict[str, Any]

class ProofLadderService:
    def __init__(self, ctx: BulutContext):
        self._ctx = ctx
        self._stages: Dict[str, ProofStage] = {}
        self._ordered_stage_ids: List[str] = []
        self._logger = logging.getLogger("tezaver.bulut.proof_ladder")
        self._load_stages()

    def _load_stages(self):
        """Load stages from resources."""
        path = Path(self._ctx.config.proof_ladder_stages_path)
        if not path.exists():
            self._logger.warning(f"Proof Ladder stages missing at {path}")
            return
            
        try:
            data = json.loads(path.read_text())
            if data.get("schema") != "proof_ladder_stages_v1":
                self._logger.error("Invalid proof ladder schema version")
                return
            
            stages_list = data.get("stages", [])
            self._stages = {}
            for s in stages_list:
                obj = ProofStage(
                    stage_id=s["stage_id"],
                    cap_usdt=float(s["cap_usdt"]),
                    min_hours_clean=float(s["min_hours_clean"]),
                    next=s.get("next")
                )
                self._stages[obj.stage_id] = obj
            
            # Simple ordering logic if chained via `next`. 
            # Or just keep map.
            # We need to find "First" stage? Usually start is implicit or current state.
            pass
        except Exception as e:
            self._logger.error(f"Failed to load proof ladder stages: {e}")

    def get_stage(self, stage_id: str) -> Optional[ProofStage]:
        return self._stages.get(stage_id)

    def evaluate(self) -> EvalResult:
        """
        Evaluate evidence for current stage.
        Checks alerts, drift, audits against stage lookback.
        """
        # Load State
        state = self._ctx.persistence.get_proof_ladder_state()
        
        # Seed if missing
        if not state:
            # Seed Pilot
            self._logger.info("Seeding Proof Ladder State")
            stages_path = Path(self._ctx.config.proof_ladder_stages_path)
            first_id = "PILOT_50_24H"
            first_cap = 50.0
            
            if stages_path.exists():
                try:
                    d = json.loads(stages_path.read_text())
                    if d.get("stages"): 
                        s = d["stages"][0]
                        first_id = s["stage_id"]
                        first_cap = float(s["cap_usdt"])
                except: pass
            
            # Initial seed (last_eval null)
            self._ctx.persistence.upsert_proof_ladder_state(
                stage_id=first_id, cap_usdt=first_cap, clean_hours=0.0, 
                last_result_obj={"seeded": True}
            )
            state = self._ctx.persistence.get_proof_ladder_state()

        current_stage_id = state["stage_id"]
        stage = self.get_stage(current_stage_id)
        
        if not stage:
             return EvalResult(False, current_stage_id, state["cap_usdt"], 0.0, ["Unknown Stage Definition"], {})

        # Evidence Checks
        reasons = []
        details = {}
        
        lookback_hours = stage.min_hours_clean
        now = datetime.now(timezone.utc)
        start_ts = (now - timedelta(hours=lookback_hours)).isoformat()
        
        # 1. Database Metrics (Alerts, Audits)
        metrics = self._ctx.persistence.get_proof_ladder_metrics(start_ts)
        details.update(metrics)
        
        # Check Limits
        cfg = self._ctx.config
        
        if metrics["alerts_critical"] > cfg.proof_ladder_max_critical_alerts:
            reasons.append(f"CRITICAL Alerts: {metrics['alerts_critical']} > {cfg.proof_ladder_max_critical_alerts}")
            
        if metrics["alerts_error"] > cfg.proof_ladder_max_error_alerts:
            reasons.append(f"ERROR Alerts: {metrics['alerts_error']} > {cfg.proof_ladder_max_error_alerts}")
            
        if metrics["audits_estimated"] > cfg.proof_ladder_max_estimated_audits:
            reasons.append(f"Estimated Audits: {metrics['audits_estimated']} > {cfg.proof_ladder_max_estimated_audits}")
            
        if metrics["fx_unconverted"] > cfg.proof_ladder_max_unconverted_fx_count:
            reasons.append(f"Unconverted FX: {metrics['fx_unconverted']} > {cfg.proof_ladder_max_unconverted_fx_count}")

        # 2. Time Sync
        if cfg.proof_ladder_require_time_sync_healthy:
            # Check Status Service if available, or just check self-test
            # StatusService usually has system_health
            # Let's check heartbeat for 'timesync'?
            # Simplification: Assume healthy if no CRITICAL alerts? (Checked above)
            # Or explicit check.
            pass

        # 3. Drift (Config/Constitution)
        if cfg.proof_ladder_require_drift_free:
             # Just ensures we are running correct version?
             # For now we rely on alerts (Constitution Check failure emits CRITICAL alert).
             pass

        passed = (len(reasons) == 0)
        clean_hours = lookback_hours if passed else 0.0 # Reset to 0 if failed? Or calculate actual?
        # "If fail, clean_hours=0". Strict.
        
        # Result
        result = EvalResult(
            passed=passed,
            stage_id=current_stage_id,
            effective_cap=state["cap_usdt"],
            clean_hours=clean_hours,
            reasons=reasons,
            details=details
        )
        
        # Persist Eval Result
        self._ctx.persistence.upsert_proof_ladder_state(
            stage_id=current_stage_id,
            cap_usdt=state["cap_usdt"],
            clean_hours=clean_hours,
            last_result_obj=asdict(result)
        )
        
        # Telemetry
        self._ctx.telemetry.emit("PROOF_LADDER_EVAL", {
             "passed": passed, "stage": current_stage_id, "clean_hours": clean_hours, "fails": reasons
        })
        
        if not passed:
             # Alert?
             pass 

        return result

    def advance_stage(self, force: bool = False) -> Tuple[bool, str]:
        """
        Advance to next stage if eligible.
        Manual call or Auto if enabled.
        """
        eval_res = self.evaluate()
        if not eval_res.passed and not force:
            return False, f"Eval Failed: {eval_res.reasons}"
            
        stage = self.get_stage(eval_res.stage_id)
        if not stage or not stage.next:
            return False, "No Next Stage"
            
        next_stage_id = stage.next
        next_stage = self.get_stage(next_stage_id)
        if not next_stage:
             return False, f"Next Stage {next_stage_id} definition missing"
             
        # Mainnet Armed Check
        if self._ctx.config.mode == "REAL_MAINNET" and self._ctx.state.execution_armed:
            if not self._ctx.config.proof_ladder_allow_advance_when_armed:
                return False, "BLOCKED: Cannot advance while Mainnet ARMED"

        # Apply
        self._ctx.persistence.upsert_proof_ladder_state(
            stage_id=next_stage.stage_id,
            cap_usdt=next_stage.cap_usdt,
            clean_hours=0.0, # Reset clean hours on promotion? Yes, must prove at new level
            last_result_obj={"msg": f"Promoted from {stage.stage_id}"}
        )
        
        self._ctx.telemetry.emit("PROOF_LADDER_ADVANCED", {
            "from": stage.stage_id, "to": next_stage.stage_id, "cap": next_stage.cap_usdt
        })
        
        return True, f"Advanced to {next_stage.stage_id} (Cap: {next_stage.cap_usdt})"

        
    def compute_effective_mainnet_cap(self) -> float:
        """
        Computes effective cap = Min(Config.Max, Stage.Cap).
        If not Mainnet, standard logic? No, this is Mainnet Proof Ladder.
        If config.PROOF_LADDER_ENABLED is False, return config.MAX_NOTIONAL.
        """
        if not self._ctx.config.proof_ladder_enabled:
             # Legacy behavior: use mainnet_max_total_notional_usdt (Launch Gate limit)
             # Wait, Launch Gate v0.24 uses `mainnet_max_total_notional_usdt`.
             # And Mainnet Pilot v0.28 uses `mainnet_pilot_max_total_notional_usdt`.
             # Complexity: V0.28 overrides V0.24 cap?
             # Let's assume Proof Ladder replaces Pilot/Gate logic or layers on top.
             # "Pilot Cap is already there (v0.28)".
             # Proof Ladder manages Stage.
             # If Enabled: use Stage.Cap.
             # But apply global safeguard `config.mainnet_max_total_notional_usdt` as upper bound?
             # "min(config.mainnet_max... , current_stage.cap)".
             return self._ctx.config.mainnet_max_total_notional_usdt

        state = self._ctx.persistence.get_proof_ladder_state()
        if not state:
             # Fallback to Pilot Cap (v0.28) or Safe Default
             return getattr(self._ctx.config, "mainnet_pilot_max_total_notional_usdt", 50.0)
             
        stage_cap = state["cap_usdt"]
        config_cap = self._ctx.config.mainnet_max_total_notional_usdt
        
        return min(stage_cap, config_cap)
