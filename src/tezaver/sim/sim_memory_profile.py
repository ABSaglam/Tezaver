"""
Tezaver Memory Profile Builder
==============================

Generates a Memory Profile JSON from threshold sweep results.
The profile provides recommended thresholds for different trading modes.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ThresholdPoint:
    """A single threshold point from the sweep."""
    min_context_score: float
    trade_count: int
    win_rate: float
    avg_pnl: float
    sum_pnl: float


# =============================================================================
# LOAD & PARSE
# =============================================================================

def load_btc_15m_threshold_sweep() -> dict:
    """Load the threshold sweep JSON for BTCUSDT 15m."""
    path = Path("data/coin_profiles/BTCUSDT/15m/sim_memory_threshold_sweep_v1.json")
    if not path.exists():
        raise FileNotFoundError(f"Threshold sweep not found: {path}")
    return json.loads(path.read_text())


def parse_threshold_points(sweep: dict) -> List[ThresholdPoint]:
    """Parse threshold points from sweep data."""
    points = []
    for item in sweep.get("thresholds", []):
        points.append(
            ThresholdPoint(
                min_context_score=float(item.get("min_context_score", 0.0)),
                trade_count=int(item.get("trade_count", 0)),
                win_rate=float(item.get("win_rate", 0.0)),
                avg_pnl=float(item.get("avg_pnl", 0.0)),
                sum_pnl=float(item.get("sum_pnl", 0.0)),
            )
        )
    # Sort by min_context_score ascending
    points.sort(key=lambda p: p.min_context_score)
    return points


# =============================================================================
# THRESHOLD SELECTION LOGIC
# =============================================================================

def select_relaxed_threshold(points: List[ThresholdPoint]) -> Optional[float]:
    """
    Select relaxed threshold:
    - min_context_score >= 50
    - trade_count >= 10
    - Best avg_pnl among candidates
    """
    candidates = [
        p for p in points
        if p.min_context_score >= 50.0 and p.trade_count >= 10
    ]
    
    if not candidates:
        logger.warning("No candidates for relaxed threshold (score>=50, trades>=10)")
        return None
    
    # Select best by avg_pnl
    best = max(candidates, key=lambda p: p.avg_pnl)
    return best.min_context_score


def select_strict_threshold(points: List[ThresholdPoint]) -> Optional[float]:
    """
    Select strict threshold:
    - min_context_score >= 70
    - trade_count >= 3
    - Best avg_pnl among candidates
    """
    candidates = [
        p for p in points
        if p.min_context_score >= 70.0 and p.trade_count >= 3
    ]
    
    if not candidates:
        logger.warning("No candidates for strict threshold (score>=70, trades>=3)")
        return None
    
    # Select best by avg_pnl
    best = max(candidates, key=lambda p: p.avg_pnl)
    return best.min_context_score


def select_balanced_threshold(
    relaxed: Optional[float],
    strict: Optional[float],
    points: List[ThresholdPoint],
) -> Optional[float]:
    """
    Select balanced threshold:
    - Between relaxed and strict
    - Closest to arithmetic mean of relaxed and strict
    """
    if relaxed is None and strict is None:
        return None
    
    if relaxed is None:
        return strict
    
    if strict is None:
        return relaxed
    
    if relaxed == strict:
        return strict
    
    # Calculate target (arithmetic mean)
    target = (relaxed + strict) / 2.0
    
    # Find closest threshold point
    valid_points = [
        p for p in points
        if relaxed <= p.min_context_score <= strict
    ]
    
    if not valid_points:
        # Fall back to strict
        return strict
    
    # Find closest to target
    closest = min(valid_points, key=lambda p: abs(p.min_context_score - target))
    return closest.min_context_score


# =============================================================================
# PROFILE BUILDER
# =============================================================================

def build_btc_15m_memory_profile(sweep: dict) -> dict:
    """
    Build Memory Profile from threshold sweep.
    
    Returns:
        {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": {...},
            "recommendations": {
                "default_threshold": ...,
                "modes": {"relaxed": ..., "balanced": ..., "strict": ...}
            },
            "notes": {...},
            "snapshot": {...}
        }
    """
    points = parse_threshold_points(sweep)
    
    # Select thresholds
    relaxed = select_relaxed_threshold(points)
    strict = select_strict_threshold(points)
    balanced = select_balanced_threshold(relaxed, strict, points)
    
    logger.info(f"Selected thresholds: relaxed={relaxed}, balanced={balanced}, strict={strict}")
    
    profile = {
        "symbol": sweep.get("symbol", "BTCUSDT"),
        "timeframe": sweep.get("timeframe", "15m"),
        "profile_version": "v1",
        "source": {
            "threshold_sweep_file": "data/coin_profiles/BTCUSDT/15m/sim_memory_threshold_sweep_v1.json",
            "sweep_date": sweep.get("sweep_date"),
        },
        "recommendations": {
            "default_threshold": balanced,
            "modes": {
                "relaxed": relaxed,
                "balanced": balanced,
                "strict": strict,
            },
        },
        "notes": {
            "description_tr": "BTCUSDT 15 Dakika için Rally Context Score v1 tabanlı hafıza profili.",
            "selection_criteria": {
                "relaxed": "score>=50, trades>=10, best avg_pnl",
                "strict": "score>=70, trades>=3, best avg_pnl",
                "balanced": "between relaxed and strict",
            },
        },
        "snapshot": {
            "baseline": sweep.get("baseline", {}),
            "thresholds": [
                {
                    "min_context_score": p.min_context_score,
                    "trade_count": p.trade_count,
                    "win_rate": p.win_rate,
                    "avg_pnl": p.avg_pnl,
                    "sum_pnl": p.sum_pnl,
                }
                for p in points
            ],
        },
    }
    
    return profile


def save_btc_15m_memory_profile(profile: dict) -> str:
    """Save Memory Profile to JSON file."""
    out_path = Path("data/coin_profiles/BTCUSDT/15m/memory_profile_v1.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    logger.info(f"Memory profile saved: {out_path}")
    return str(out_path)


# =============================================================================
# RUNNER
# =============================================================================

def run_btc_15m_memory_profile_build() -> dict:
    """
    Build and save Memory Profile for BTCUSDT 15m.
    
    Returns:
        The generated profile dict.
    """
    print("📊 BTCUSDT 15m Memory Profile Builder")
    print("=" * 50)
    
    # Load sweep
    print("\n1. Loading threshold sweep...")
    sweep = load_btc_15m_threshold_sweep()
    print(f"   Baseline: {sweep.get('baseline', {}).get('trade_count')} trades")
    print(f"   Threshold points: {len(sweep.get('thresholds', []))}")
    
    # Build profile
    print("\n2. Building memory profile...")
    profile = build_btc_15m_memory_profile(sweep)
    
    # Print recommendations
    recs = profile.get("recommendations", {})
    modes = recs.get("modes", {})
    print(f"\n   Selected Thresholds:")
    print(f"   - Relaxed:  {modes.get('relaxed')}")
    print(f"   - Balanced: {modes.get('balanced')}")
    print(f"   - Strict:   {modes.get('strict')}")
    print(f"   - Default:  {recs.get('default_threshold')}")
    
    # Save
    print("\n3. Saving profile...")
    out_path = save_btc_15m_memory_profile(profile)
    print(f"   Saved: {out_path}")
    
    print("\n✅ Memory Profile build completed!")
    
    return profile


if __name__ == "__main__":
    run_btc_15m_memory_profile_build()
