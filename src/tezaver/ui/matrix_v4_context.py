"""
Matrix V4 Context - Build context for Matrix V4 UI

This module provides context/counts for the Matrix V4 Streamlit UI.
Does NOT import panel_server or legacy matrix modules.
"""

import os
import json
import subprocess
from typing import Dict, Any

def build_matrix_v4_context(home: str = ".tezaver_matrix") -> Dict[str, Any]:
    """
    Build context for Matrix V4 UI.
    
    Returns dict with:
    - commit: git commit hash (best-effort)
    - branch: git branch name (best-effort)
    - home: absolute path to home
    - counts: dict with counts for each category
    
    Safe for empty/missing directories - returns 0s.
    """
    # Git info (best-effort)
    commit = "unknown"
    branch = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        pass
        
    # Counts
    counts = {
        "candidates": 0,
        "runs": 0,
        "alerts_active": 0,
        "approved": 0,
        "exports": 0,
        "strategies": 0,
    }
    
    try:
        cand_dir = os.path.join(home, "candidates")
        if os.path.exists(cand_dir):
            counts["candidates"] = len([d for d in os.listdir(cand_dir) if os.path.isdir(os.path.join(cand_dir, d))])
    except Exception:
        pass
        
    try:
        runs_dir = os.path.join(home, "runs")
        if os.path.exists(runs_dir):
            counts["runs"] = len([d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))])
    except Exception:
        pass
        
    try:
        alerts_dir = os.path.join(home, "alerts", "active")
        if os.path.exists(alerts_dir):
            counts["alerts_active"] = len([f for f in os.listdir(alerts_dir) if f.endswith(".json")])
    except Exception:
        pass
        
    try:
        approved_dir = os.path.join(home, "approved")
        if os.path.exists(approved_dir):
            counts["approved"] = len([d for d in os.listdir(approved_dir) if os.path.isdir(os.path.join(approved_dir, d))])
    except Exception:
        pass
        
    try:
        exports_dir = os.path.join(home, "exports")
        if os.path.exists(exports_dir):
            counts["exports"] = len([d for d in os.listdir(exports_dir) if os.path.isdir(os.path.join(exports_dir, d))])
    except Exception:
        pass
        
    try:
        strat_dir = os.path.join(home, "cloud_registry", "strategies")
        if os.path.exists(strat_dir):
            counts["strategies"] = len([d for d in os.listdir(strat_dir) if os.path.isdir(os.path.join(strat_dir, d))])
    except Exception:
        pass
        
    return {
        "commit": commit,
        "branch": branch,
        "home": os.path.abspath(home),
        "counts": counts,
    }
