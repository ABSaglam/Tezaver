import pytest
import os
import json
from pathlib import Path
from tezaver.matrix.safety.kill_switch_v1 import (
    get_kill_switch_state,
    write_kill_switch_marker
)

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def test_env_var_triggers_kill_switch(tmp_path, monkeypatch):
    """Env var TEZAVER_KILL_SWITCH=1 triggers kill switch."""
    monkeypatch.setenv("TEZAVER_KILL_SWITCH", "1")
    
    state = get_kill_switch_state(str(tmp_path), "war", "run_env")
    
    assert state["triggered"] is True
    assert state["reason"] == "env"

def test_marker_file_triggers_kill_switch(tmp_path, monkeypatch):
    """Marker file triggers kill switch."""
    monkeypatch.delenv("TEZAVER_KILL_SWITCH", raising=False)
    
    # Write marker
    write_kill_switch_marker(str(tmp_path), "war", "run_marker", triggered=True, reason="manual")
    
    state = get_kill_switch_state(str(tmp_path), "war", "run_marker")
    
    assert state["triggered"] is True
    assert state["reason"] == "manual"

def test_no_trigger_by_default(tmp_path, monkeypatch):
    """No trigger by default."""
    monkeypatch.delenv("TEZAVER_KILL_SWITCH", raising=False)
    
    state = get_kill_switch_state(str(tmp_path), "war", "run_clean")
    
    assert state["triggered"] is False
    assert state["reason"] is None

def test_env_var_takes_priority(tmp_path, monkeypatch):
    """Env var takes priority over marker file."""
    monkeypatch.setenv("TEZAVER_KILL_SWITCH", "1")
    
    # Write marker as NOT triggered
    state_dir = tmp_path / "war" / "run_priority" / "state"
    state_dir.mkdir(parents=True)
    write_json(state_dir / "pool_kill_switch_state_v1.json", {"triggered": False, "reason": "off"})
    
    state = get_kill_switch_state(str(tmp_path), "war", "run_priority")
    
    # Env var should take priority
    assert state["triggered"] is True
    assert state["reason"] == "env"

def test_marker_file_not_triggered(tmp_path, monkeypatch):
    """Marker file with triggered=false does not trigger."""
    monkeypatch.delenv("TEZAVER_KILL_SWITCH", raising=False)
    
    # Write marker as NOT triggered
    write_kill_switch_marker(str(tmp_path), "war", "run_off", triggered=False, reason="disabled")
    
    state = get_kill_switch_state(str(tmp_path), "war", "run_off")
    
    assert state["triggered"] is False
