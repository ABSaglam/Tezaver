"""
Tezaver Sim Profile Registry
=============================

Matrix candidate profile management for strategy export.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional


MATRIX_CANDIDATE_PATH = Path("data/coin_profiles/BTCUSDT/matrix_candidate_profiles_v1.json")


@dataclass
class MatrixCandidateProfile:
    """
    A candidate strategy profile for Matrix integration.
    """
    profile_id: str
    symbol: str
    timeframe: str
    source: str  # e.g. "COIN_LAB_CELL_V1"
    strategy_type: str  # e.g. "silver_core", "silver_core_experimental"
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    preset_id: Optional[str] = None
    status: str = "CANDIDATE"
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


def load_matrix_candidate_profiles() -> Dict[str, MatrixCandidateProfile]:
    """Load existing candidate profiles from JSON as dict keyed by profile_id."""
    if not MATRIX_CANDIDATE_PATH.exists():
        return {}
    try:
        data = json.loads(MATRIX_CANDIDATE_PATH.read_text())
        profiles = data.get("profiles", [])
        result = {}
        for p in profiles:
            pid = p.get("profile_id")
            if pid:
                result[pid] = MatrixCandidateProfile(
                    profile_id=p.get("profile_id", ""),
                    symbol=p.get("symbol", ""),
                    timeframe=p.get("timeframe", ""),
                    source=p.get("source", ""),
                    strategy_type=p.get("strategy_type", ""),
                    config=p.get("config", {}),
                    metrics=p.get("metrics", {}),
                    preset_id=p.get("preset_id"),
                    status=p.get("status", "CANDIDATE"),
                    created_at=p.get("created_at", ""),
                )
        return result
    except Exception:
        return {}


def _load_profiles_list() -> List[Dict[str, Any]]:
    """Load profiles as raw list for internal use."""
    if not MATRIX_CANDIDATE_PATH.exists():
        return []
    try:
        data = json.loads(MATRIX_CANDIDATE_PATH.read_text())
        return data.get("profiles", [])
    except Exception:
        return []


def save_matrix_candidate_profiles(profiles: List[Dict[str, Any]]) -> None:
    """Save candidate profiles to JSON."""
    MATRIX_CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "profiles": profiles
    }
    MATRIX_CANDIDATE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def upsert_matrix_candidate_profile(profile: MatrixCandidateProfile) -> str:
    """
    Insert or update a candidate profile.
    Returns the profile_id.
    """
    profiles = _load_profiles_list()
    
    # Find existing by profile_id
    updated = False
    for i, p in enumerate(profiles):
        if p.get("profile_id") == profile.profile_id:
            profiles[i] = asdict(profile)
            updated = True
            break
    
    if not updated:
        profiles.append(asdict(profile))
    
    save_matrix_candidate_profiles(profiles)
    return profile.profile_id


def get_matrix_candidate_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific candidate profile by ID."""
    profiles = _load_profiles_list()
    for p in profiles:
        if p.get("profile_id") == profile_id:
            return p
    return None


# =============================================================================
# BTC SILVER CORE PROFILE EXPORT
# =============================================================================

def export_btc_silver_core_profiles_to_matrix(
    include_4h_experimental: bool = False
) -> Dict[str, Any]:
    """
    Export BTCUSDT Silver core strategy profiles to Matrix candidate profiles.
    
    15m and 1h are official, 4h is optional and marked as 'experimental'.
    """
    from tezaver.sim import sim_core_experiments as core_exp

    symbol = "BTCUSDT"
    
    # Timeframes to export
    timeframes = ["15m", "1h"]
    if include_4h_experimental:
        timeframes.append("4h")

    results: Dict[str, Any] = {}

    for tf in timeframes:
        exp_result = core_exp.run_btc_core_strategy_sim(tf)
        
        if not exp_result.get("ok", False):
            results[tf] = {
                "ok": False,
                "reason": exp_result.get("reason", "unknown_error"),
            }
            continue
        
        perf = exp_result["performance"]

        if tf == "4h" and include_4h_experimental:
            profile_id = "BTC_SILVER_4H_CORE_V0_EXPERIMENTAL"
            strategy_type = "silver_core_experimental"
        else:
            profile_id = f"BTC_SILVER_{tf.upper()}_CORE_V1"
            strategy_type = "silver_core"

        profile = MatrixCandidateProfile(
            profile_id=profile_id,
            symbol=symbol,
            timeframe=tf,
            source="COIN_LAB_CELL_V1",
            strategy_type=strategy_type,
            preset_id=exp_result.get("config_id"),
            config=exp_result.get("config", {}),
            metrics={
                "trade_count": perf["trade_count"],
                "win_rate": perf["win_rate"],
                "avg_pnl": perf["avg_pnl"],
                "sum_pnl": perf["sum_pnl"],
                "max_drawdown": perf["max_drawdown"],
                "final_equity": perf["final_equity"],
                "capital_start": perf["capital_start"],
                "capital_end": perf["capital_end"],
            },
        )

        upsert_matrix_candidate_profile(profile)

        results[tf] = {
            "ok": True,
            "profile_id": profile_id,
            "timeframe": tf,
            "capital_100": perf["capital_end"],
            "trade_count": perf["trade_count"],
        }

    return results

