"""
Pool Reports V1
===============

Utilities for writing pool reports to the standard Matrix run structure.
Standard path: out/matrix_runs/<stage>/<run_id>/reports/
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Union

def resolve_reports_dir(stage: str, run_id: str, root_dir: str = "out/matrix_runs") -> Path:
    """
    Resolve the absolute path to the reports directory for a specific run.
    
    Args:
        stage: Run stage (WAR, LIVE, etc.)
        run_id: Unique run ID
        root_dir: Root output directory (default: out/matrix_runs)
        
    Returns:
        Path object pointing to the reports directory
    """
    # Normalize stage
    stage_norm = stage.lower()
    return Path(root_dir) / stage_norm / run_id / "reports"

def write_report_json(path: Path, data: Dict[str, Any]):
    """
    Write a dictionary to a JSON file, creating parent directories if needed.
    
    Args:
        path: Target file path
        data: Dictionary to write
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()
