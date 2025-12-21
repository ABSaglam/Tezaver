"""
Tezaver Matrix - Run Path Standardization
Defines standard paths for run-scoped artifacts and reports.
"""
import os
from pathlib import Path
from typing import Optional

def get_run_root(mode: str, run_id: str, home: Optional[str] = None) -> Path:
    """
    Returns the root directory for a specific run.
    Modes: SNIPER, WAR, LIVE
    Path pattern: out/matrix_runs/<mode>/<run_id>/
    """
    # Standard base directories per mode
    mode_map = {
        "SNIPER": "out/matrix_runs/sniper",
        "WAR": "out/matrix_runs/war",
        "LIVE": "out/matrix_runs/live"
    }
    
    base = mode_map.get(mode.upper(), "out/matrix_runs/misc")
    
    if home:
        return Path(home) / base / run_id
    else:
        # Default to current working directory root
        return Path(base) / run_id

def get_data_report_path(mode: str, run_id: str, home: Optional[str] = None) -> Path:
    """
    Returns the path to the run-scoped data report.
    Path: <run_root>/reports/data_report_v1.json
    """
    root = get_run_root(mode, run_id, home)
    return root / "reports" / "data_report_v1.json"

def get_judge_report_path(mode: str, run_id: str, home: Optional[str] = None) -> Path:
    """
    Returns the path to the run-scoped judge report (judge.json or report.json).
    Note: Some modules use report.json, others judge.json. 
    Standardizing on report.json for Matrix V4.
    """
    root = get_run_root(mode, run_id, home)
    return root / "report.json"
