"""
Tezaver Mac - System State Management (M23)
============================================

Tracks and persists system operation status (pipeline runs, backups, tests).
Provides utilities for viewing system logs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any, Dict

from tezaver.core import coin_cell_paths
from tezaver.core.config import get_turkey_now

# System state file location
SYSTEM_STATE_FILE = coin_cell_paths.get_project_root() / "data" / "system_state.json"


@dataclass
class SystemState:
    """Tracks the last run status of various system operations."""
    
    # Full pipeline
    last_full_pipeline_run_at: Optional[str] = None
    last_full_pipeline_status: Optional[str] = None
    last_full_pipeline_duration_sec: Optional[float] = None
    
    # Fast pipeline
    last_fast_pipeline_run_at: Optional[str] = None
    last_fast_pipeline_status: Optional[str] = None
    last_fast_pipeline_duration_sec: Optional[float] = None
    
    # Mini backup
    last_mini_backup_at: Optional[str] = None
    last_mini_backup_status: Optional[str] = None
    last_mini_backup_duration_sec: Optional[float] = None
    
    # Full backup
    last_full_backup_at: Optional[str] = None
    last_full_backup_status: Optional[str] = None
    last_full_backup_duration_sec: Optional[float] = None
    
    # Tests
    last_tests_run_at: Optional[str] = None
    last_tests_status: Optional[str] = None
    last_tests_duration_sec: Optional[float] = None
    last_tests_summary: Optional[str] = None

    # Time-Labs 1h
    last_time_labs_1h_run_at: Optional[str] = None
    last_time_labs_1h_status: str = "never"
    last_time_labs_1h_duration_sec: Optional[float] = None

    # Time-Labs 4h
    last_time_labs_4h_run_at: Optional[str] = None
    last_time_labs_4h_status: str = "never"
    last_time_labs_4h_duration_sec: Optional[float] = None

    # Offline Maintenance / Lab Pipeline
    last_offline_maintenance_run_at: Optional[str] = None
    last_offline_maintenance_status: str = "never"
    last_offline_maintenance_duration_sec: Optional[float] = None
    last_offline_maintenance_run_id: Optional[str] = None
    
    # Generic Task Timestamps (Label -> ISO String)
    task_timestamps: Dict[str, str] = field(default_factory=dict)


def _ensure_dir() -> None:
    """Ensure system state file directory exists."""
    SYSTEM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    """Return current Turkey time as ISO string (seconds precision)."""
    return get_turkey_now().isoformat(timespec="seconds")


def load_state() -> SystemState:
    """
    Load system state from JSON file.
    Returns a new SystemState with defaults if file doesn't exist or is invalid.
    """
    if not SYSTEM_STATE_FILE.exists():
        return SystemState()
    
    try:
        with open(SYSTEM_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SystemState(**data)
    except Exception:
        # If anything goes wrong, return fresh state
        return SystemState()


def save_state(state: SystemState) -> None:
    """Save system state to JSON file."""
    _ensure_dir()
    
    with open(SYSTEM_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(state), f, indent=2, ensure_ascii=False)


def record_pipeline_run(mode: str, status: str, duration_sec: float) -> SystemState:
    """
    Record a pipeline run execution.
    
    Args:
        mode: "full" or "fast"
        status: "success" or "error"
        duration_sec: Duration in seconds
        
    Returns:
        Updated SystemState
    """
    state = load_state()
    
    if mode == "full":
        state.last_full_pipeline_run_at = _now_iso()
        state.last_full_pipeline_status = status
        state.last_full_pipeline_duration_sec = duration_sec
    elif mode == "fast":
        state.last_fast_pipeline_run_at = _now_iso()
        state.last_fast_pipeline_status = status
        state.last_fast_pipeline_duration_sec = duration_sec
    
    save_state(state)
    return state


def record_backup_run(kind: str, status: str, duration_sec: float) -> SystemState:
    """
    Record a backup execution.
    
    Args:
        kind: "mini" or "full"
        status: "success" or "error"
        duration_sec: Duration in seconds
        
    Returns:
        Updated SystemState
    """
    state = load_state()
    
    if kind == "mini":
        state.last_mini_backup_at = _now_iso()
        state.last_mini_backup_status = status
        state.last_mini_backup_duration_sec = duration_sec
    elif kind == "full":
        state.last_full_backup_at = _now_iso()
        state.last_full_backup_status = status
        state.last_full_backup_duration_sec = duration_sec
    
    save_state(state)
    return state


def record_tests_run(status: str, duration_sec: float, summary: Optional[str]) -> SystemState:
    """
    Record a test execution.
    
    Args:
        status: "success" or "error"
        duration_sec: Duration in seconds
        summary: Optional summary text from pytest output
        
    Returns:
        Updated SystemState
    """
    state = load_state()
    
    state.last_tests_run_at = _now_iso()
    state.last_tests_status = status
    state.last_tests_duration_sec = duration_sec
    state.last_tests_summary = summary
    
    save_state(state)
    save_state(state)
    return state


def record_time_labs_run(timeframe: str, status: str, duration_sec: float) -> SystemState:
    """
    Record a Time-Labs scan execution.
    
    Args:
        timeframe: "1h" or "4h"
        status: "success" or "error"
        duration_sec: Duration in seconds
        
    Returns:
        Updated SystemState
    """
    state = load_state()
    
    if timeframe == "1h":
        state.last_time_labs_1h_run_at = _now_iso()
        state.last_time_labs_1h_status = status
        state.last_time_labs_1h_duration_sec = duration_sec
    elif timeframe == "4h":
        state.last_time_labs_4h_run_at = _now_iso()
        state.last_time_labs_4h_status = status
        state.last_time_labs_4h_duration_sec = duration_sec
    
    save_state(state)
    return state


def record_offline_maintenance_run(summary: 'Any') -> SystemState:
    """
    Record an Offline Maintenance pipeline run.
    Arg summary is typed Any to avoid circular import, but expects MaintenanceRunSummary.
    """
    state = load_state()
    
    # We assume summary object has aligned fields or is a dict
    # But Python objects are safer.
    # Let's interact via attributes.
    
    state.last_offline_maintenance_run_at = _now_iso()
    state.last_offline_maintenance_status = getattr(summary, "overall_status", "unknown")
    
    # calculate total duration from start/end if available, or pass it?
    # Summary has started_at/finished_at (datetime).
    start = getattr(summary, "started_at", None)
    end = getattr(summary, "finished_at", None)
    
    if start and end and isinstance(start, datetime) and isinstance(end, datetime):
        dur = (end - start).total_seconds()
        state.last_offline_maintenance_duration_sec = dur
    else:
        state.last_offline_maintenance_duration_sec = 0.0
        
    state.last_offline_maintenance_run_id = getattr(summary, "run_id", None)
    
    save_state(state)
    save_state(state)
    return state


def record_task_run(label: str) -> SystemState:
    """
    Record a generic task execution timestamp.
    """
    state = load_state()
    # Ensure dict exists (backward compatibility)
    if state.task_timestamps is None:
        state.task_timestamps = {}
        
    state.task_timestamps[label] = _now_iso()
    save_state(state)
    return state


def get_log_tail(max_lines: int = 200) -> List[str]:
    """
    Get the last N lines from the main log file.
    
    Args:
        max_lines: Maximum number of lines to return
        
    Returns:
        List of log lines (with newlines)
    """
    project_root = coin_cell_paths.get_project_root()
    log_file = project_root / "logs" / "tezaver_mac.log"
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except Exception:
        return []
