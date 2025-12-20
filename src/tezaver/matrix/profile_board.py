"""
Profile Board - V4 Compatible Shim for UI

Provides ProfileBoardRow dataclass and build_profile_board function
for the Matrix Operator Tab UI.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProfileBoardRow:
    """Represents a strategy profile in the Matrix Board."""
    symbol: str
    timeframe: str
    profile_id: str
    status: str  # DRAFT, APPROVED, REJECTED, etc.
    pnl_pct: Optional[float] = None
    trades: Optional[int] = None
    max_risk_per_trade: Optional[float] = None
    live_eligible: bool = False
    
def build_profile_board(home: str = ".tezaver_matrix") -> List[ProfileBoardRow]:
    """
    Build profile board from V4 data directories.
    
    Returns a list of ProfileBoardRow objects representing system status.
    Safe for empty home directories - returns empty list if no data.
    """
    rows = []
    
    # Scan approved pool
    approved_dir = os.path.join(home, "approved")
    if os.path.exists(approved_dir):
        for cid in os.listdir(approved_dir):
            manifest_path = os.path.join(approved_dir, cid, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path) as f:
                        m = json.load(f)
                    rows.append(ProfileBoardRow(
                        symbol=m.get("symbol", "UNKNOWN"),
                        timeframe=m.get("timeframe", "15m"),
                        profile_id=cid,
                        status="APPROVED",
                        pnl_pct=m.get("pnl_pct"),
                        trades=m.get("trades"),
                        max_risk_per_trade=m.get("max_risk_per_trade", 0.01),
                        live_eligible=True,
                    ))
                except Exception:
                    pass
                    
    # Scan candidates for non-approved profiles
    candidates_dir = os.path.join(home, "candidates")
    if os.path.exists(candidates_dir):
        for cid in os.listdir(candidates_dir):
            # Skip if already in approved
            if any(r.profile_id == cid for r in rows):
                continue
                
            manifest_path = os.path.join(candidates_dir, cid, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path) as f:
                        m = json.load(f)
                        
                    # Check stage
                    stage_path = os.path.join(home, "candidates_stage", f"{cid}.json")
                    stage = "DRAFT"
                    if os.path.exists(stage_path):
                        try:
                            with open(stage_path) as f:
                                stage = json.load(f).get("stage", "DRAFT")
                        except Exception:
                            pass
                            
                    rows.append(ProfileBoardRow(
                        symbol=m.get("symbol", "UNKNOWN"),
                        timeframe=m.get("timeframe", "15m"),
                        profile_id=cid,
                        status=stage,
                        pnl_pct=m.get("pnl_pct"),
                        trades=m.get("trades"),
                        max_risk_per_trade=m.get("max_risk_per_trade", 0.01),
                        live_eligible=(stage == "APPROVED"),
                    ))
                except Exception:
                    pass
                    
    # Scan cloud registry strategies
    strat_dir = os.path.join(home, "cloud_registry", "strategies")
    if os.path.exists(strat_dir):
        for sid in os.listdir(strat_dir):
            # Skip if already in rows
            if any(r.profile_id == sid for r in rows):
                continue
                
            strat_path = os.path.join(strat_dir, sid, "strategy.json")
            if os.path.exists(strat_path):
                try:
                    with open(strat_path) as f:
                        s = json.load(f)
                    rows.append(ProfileBoardRow(
                        symbol=s.get("symbol", "UNKNOWN"),
                        timeframe=s.get("timeframe", "15m"),
                        profile_id=sid,
                        status=s.get("status_info", {}).get("status", "UNKNOWN"),
                        pnl_pct=None,
                        trades=None,
                        max_risk_per_trade=s.get("risk", {}).get("max_risk_per_trade", 0.01),
                        live_eligible=s.get("status_info", {}).get("status") == "ACTIVE",
                    ))
                except Exception:
                    pass
                    
    return rows
