from typing import Any, Dict, List
from tezaver.matrix.game.game_models_v1 import CourtDecisionTrace, GameStageReason

class GameCourtTraceNormalizer:
    """
    Normalizes Matrix Pool components outputs into CourtDecisionTrace.
    """
    
    @staticmethod
    def normalize(
        verdict_obj: Any,  # PoolCourtVerdictV1
        risk_report: Any,  # PoolRiskReportV1 or V2
        scorecard: Any,    # PoolJuryScorecardV1
        intents_report: Any # PoolIntentsReportV1
    ) -> CourtDecisionTrace:
        
        trace = CourtDecisionTrace(
            verdict=getattr(verdict_obj, "verdict", "UNKNOWN") if verdict_obj else "SKIP",
            scorecard=asdict_safe(scorecard),
            limits=asdict_safe(risk_report).get("limits", {}) if risk_report else {}
        )
        
        # 1. Collect Reasons from Verdict (Blocked/Skipped)
        if verdict_obj:
            # Blocked Reasons
            if hasattr(verdict_obj, "blocked_reasons"):
                for reason in verdict_obj.blocked_reasons: # List[str] or List[Dict] usually?
                    # Check structure. Usually reasons are strings or dicts.
                    # Adapting generic structure
                    trace.stage_reasons.append(
                        GameStageReason(stage="DETECTED_BLOCK", rule_code="BLOCK", reason_code=str(reason), detail=str(reason))
                    )
            
            # Skipped Reasons
            if hasattr(verdict_obj, "skipped_reasons"):
                for reason in verdict_obj.skipped_reasons:
                    trace.stage_reasons.append(
                        GameStageReason(stage="DETECTED_SKIP", rule_code="SKIP", reason_code=str(reason), detail=str(reason))
                    )

        # 2. Risk Report (Prosecutor)
        if risk_report:
            # Check for blocked reasons in risk report
            blocked_map = getattr(risk_report, "blocked_reasons_count", {})
            for reason_code, count in blocked_map.items():
                trace.stage_reasons.append(
                    GameStageReason(stage="PROSECUTOR", rule_code="RISK_LIMIT", reason_code=reason_code, detail=f"Count: {count}")
                )
                
        # 3. Intents Report (Defender)
        if intents_report:
             skipped_map = getattr(intents_report, "skipped_reasons_count", {})
             for reason_code, count in skipped_map.items():
                trace.stage_reasons.append(
                    GameStageReason(stage="DEFENDER", rule_code="INTENT_FILTER", reason_code=reason_code, detail=f"Count: {count}")
                )

        # 4. Gates (Judge)
        if verdict_obj and hasattr(verdict_obj, "gates"):
            for gate in verdict_obj.gates:
                if gate.get("status") != "PASS":
                     trace.stage_reasons.append(
                        GameStageReason(stage="JUDGE", rule_code="GATE_FAIL", reason_code=gate.get("name"), detail=gate.get("reason"))
                    )

        return trace

def asdict_safe(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if isinstance(obj, dict):
        return obj
    return {}
