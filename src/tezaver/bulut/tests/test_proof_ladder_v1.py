# Tezaver Bulut - Proof Ladder Tests
import pytest
from unittest.mock import MagicMock, patch
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.proof_ladder import ProofLadderService, EvalResult

@pytest.fixture
def mock_config(tmp_path):
    # Mock config with temp paths
    stages = {
        "schema": "proof_ladder_stages_v1",
        "stages": [
             {"stage_id":"PILOT","cap_usdt":50.0,"min_hours_clean":1.0,"next":"STAGE_1"},
             {"stage_id":"STAGE_1","cap_usdt":100.0,"min_hours_clean":24.0,"next":None}
        ]
    }
    stages_file = tmp_path / "stages.json"
    stages_file.write_text(json.dumps(stages))
    
    cfg = BulutConfig()
    object.__setattr__(cfg, "proof_ladder_enabled", True)
    object.__setattr__(cfg, "proof_ladder_stages_path", str(stages_file))
    object.__setattr__(cfg, "proof_ladder_require_clean_hours", 1.0)
    object.__setattr__(cfg, "sqlite_path", str(tmp_path / "test.db"))
    object.__setattr__(cfg, "mainnet_max_total_notional_usdt", 500.0) # Global Hard Cap
    
    return cfg

@pytest.fixture
def ctx(mock_config):
    # Setup context with persistence
    c = BulutContext(mock_config)
    # Init persistence
    _ = c.persistence # trigger lazy load
    # Mock Telemetry
    c._telemetry = MagicMock()
    return c

def test_load_and_seed(ctx):
    """Test loading stages and seeding default state."""
    ladder = ProofLadderService(ctx)
    assert ladder.get_stage("PILOT") is not None
    
    # Evaluate triggers seed
    res = ladder.evaluate()
    state = ctx.persistence.get_proof_ladder_state()
    assert state
    assert state["stage_id"] == "PILOT"
    assert state["cap_usdt"] == 50.0

def test_compute_effective_cap(ctx):
    """Test effective cap logic (Min of Config vs Stage)."""
    ladder = ProofLadderService(ctx)
    ladder.evaluate() # seed
    
    # Stage PILOT (50), Config (500) -> 50
    eff = ladder.compute_effective_mainnet_cap()
    assert eff == 50.0
    
    # Advance state manually
    ctx.persistence.upsert_proof_ladder_state("STAGE_1", 100.0, 0.0, {})
    eff = ladder.compute_effective_mainnet_cap()
    assert eff == 100.0
    
    # Lower global config to 80
    object.__setattr__(ctx.config, "mainnet_max_total_notional_usdt", 80.0)
    eff = ladder.compute_effective_mainnet_cap()
    assert eff == 80.0

def test_eval_fails_on_critical_alert(ctx):
    """Test evaluation logic with mocked metrics."""
    ladder = ProofLadderService(ctx)
    ladder.evaluate() # seed
    
    # Mock persistence.get_proof_ladder_metrics
    # Original logic in persistence checks DB. 
    # Let's insert an ALERT into DB instead of mocking method, to test integration.
    # Alert ts must be recent (within min_hours_clean=1.0)
    
    conn = ctx.persistence._get_conn()
    cur = conn.cursor()
    # Ensure table exists in test env
    cur.execute("CREATE TABLE IF NOT EXISTS alerts (ts TEXT, level TEXT, code TEXT, message TEXT, details_json TEXT)")
    
    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("INSERT INTO alerts (ts, level, code, message) VALUES (?, 'CRITICAL', 'TEST', 'Fail')", (now_iso,))
    conn.commit()
    conn.close()
    
    res = ladder.evaluate()
    assert not res.passed
    assert "CRITICAL Alerts: 1" in res.reasons[0]
    assert res.clean_hours == 0.0

def test_advance_stage_logic(ctx):
    """Test advance flow."""
    ladder = ProofLadderService(ctx)
    ladder.evaluate()
    
    # Try Advance (Fail because just seeded, clean_hours=0, and clean_hours reset to 0 IF eval fails?)
    # Wait, Seed sets clean_hours=0. Eval logic calculates valid lookback.
    # If no alerts, eval should PASS and set clean_hours = lookback.
    
    # Ensure clean state
    # (No alerts in DB)
    res = ladder.evaluate()
    assert res.passed
    assert res.clean_hours == 1.0 # PILOT has 1.0
    
    # Advance
    ok, msg = ladder.advance_stage()
    assert ok
    assert "Advanced to STAGE_1" in msg
    
    # Verify state
    state = ctx.persistence.get_proof_ladder_state()
    assert state["stage_id"] == "STAGE_1"
    assert state["cap_usdt"] == 100.0
    assert state["clean_hours"] == 0.0 # reset on advance

def test_mainnet_armed_blocks_advance(ctx):
    """Test safety block on Mainnet Armed."""
    ladder = ProofLadderService(ctx)
    ladder.evaluate()
    
    # Set Mainnet Armed
    object.__setattr__(ctx.config, "mode", "REAL_MAINNET")
    ctx.state.execution_armed = True
    
    # Try Advance (Even if Clean)
    res = ladder.evaluate() # Should pass
    assert res.passed
    
    ok, msg = ladder.advance_stage()
    assert not ok
    assert "BLOCKED: Cannot advance while Mainnet ARMED" in msg
    
    # Allow via config
    object.__setattr__(ctx.config, "proof_ladder_allow_advance_when_armed", True)
    ok, msg = ladder.advance_stage()
    assert ok
    assert "Advanced to STAGE_1" in msg
