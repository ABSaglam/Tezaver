import os
import json
import pytest
from tezaver.ui.matrix_v4_context import build_matrix_v4_context

def test_context_empty_home(tmp_path):
    """Test build_matrix_v4_context with empty home directory."""
    home = str(tmp_path)
    
    ctx = build_matrix_v4_context(home)
    
    assert "commit" in ctx
    assert "branch" in ctx
    assert "home" in ctx
    assert "counts" in ctx
    
    # Empty home = all counts 0
    assert ctx["counts"]["candidates"] == 0
    assert ctx["counts"]["runs"] == 0
    assert ctx["counts"]["alerts_active"] == 0
    assert ctx["counts"]["approved"] == 0
    assert ctx["counts"]["exports"] == 0
    assert ctx["counts"]["strategies"] == 0

def test_context_with_alerts(tmp_path):
    """Test build_matrix_v4_context detects active alerts."""
    home = str(tmp_path)
    
    # Create alerts/active with one alert
    alerts_dir = tmp_path / "alerts" / "active"
    alerts_dir.mkdir(parents=True)
    
    with open(alerts_dir / "alert_001.json", "w") as f:
        json.dump({"alert_id": "alert_001", "level": "WARN"}, f)
        
    ctx = build_matrix_v4_context(home)
    
    assert ctx["counts"]["alerts_active"] == 1

def test_context_with_candidates(tmp_path):
    """Test build_matrix_v4_context counts candidates."""
    home = str(tmp_path)
    
    # Create candidates
    cand_dir = tmp_path / "candidates" / "C1"
    cand_dir.mkdir(parents=True)
    
    cand_dir2 = tmp_path / "candidates" / "C2"
    cand_dir2.mkdir(parents=True)
    
    ctx = build_matrix_v4_context(home)
    
    assert ctx["counts"]["candidates"] == 2
