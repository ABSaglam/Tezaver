
import pytest
import json
import time
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from tezaver.matrix.core.cloud_runtime import pool_step
from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1
from tezaver.matrix.pool.pool_models_v1 import PoolUniverseCellV1
from tezaver.matrix.sniper.certification_registry import CertificationRegistry, STAGE_SNIPER_PASSED, STAGE_CANDIDATE

@pytest.fixture
def mock_registry():
    """Mock bundle registry with 1 bundle."""
    reg = MagicMock(spec=BundleRegistry)
    
    manifest = ApprovedRallyBundleManifestV1(
        bundle_version="approved_rally_bundle_v1",
        bundle_id="BTC-15m-TEST",
        symbol="BTCUSDT",
        timeframe="15m",
        event_id="EVT_1",
        event_time_iso="2023-01-01T00:00:00Z",
        approved_entry_bar_offset=1,
        approved_entry_ts="2023-01-01T00:15:00Z",
        qc_verdict="PASS",
        qc_score=90,
        tier="GOLD",
        trigger_spec_v1={"type": "RSI_CROSS", "param": 30},
        policy_spec_v1={"exit_policy": "TP_SL", "notional": 100}
    )
    
    # Mock 'get' to return a bundle wrapper
    bundle_wrapper = MagicMock()
    bundle_wrapper.manifest = manifest
    reg.get.return_value = bundle_wrapper
    
    # Mock pool universe to select this bundle
    # We need to ensure run_pool_phase2a finds this bundle.
    # Actually pool_step calls discover_and_load. We mock that too.
    reg.discover_and_load = MagicMock()
    
    return reg

@pytest.fixture
def mock_cert_registry():
    """Mock certification registry."""
    with patch("tezaver.matrix.pool.pool_engine_v1.CertificationRegistry") as MockCertReg:
        instance = MockCertReg.return_value
        yield instance

@pytest.fixture
def clean_env(tmp_path):
    """Setup clean environment for artifacts."""
    # We need to redirect 'out/matrix_runs' to tmp_path to interpret results
    # We can patch 'resolve_reports_dir'
    with patch("tezaver.matrix.pool.pool_reports_v1.resolve_reports_dir") as mock_resolve:
         # Redirect to tmp_path/war/<run_id>/reports
         def side_effect(stage, run_id, root_dir=None):
              return tmp_path / stage / run_id / "reports"
         mock_resolve.side_effect = side_effect
         
         # ALSO patch court runner's resolve_reports_dir
         with patch("tezaver.matrix.pool_court.pool_court_runner_v1.resolve_reports_dir", side_effect=side_effect):
             with patch("tezaver.matrix.pool.pool_engine_v1.resolve_reports_dir", side_effect=side_effect):
                 with patch("tezaver.matrix.pool.pool_orchestrator_v1.resolve_reports_dir", side_effect=side_effect):
                 
                     # Ensure cloud_runtime/runs/<cloud_run_id> exists for events
                     (tmp_path / "cloud_runtime" / "runs" / "CLOUD_TEST").mkdir(parents=True, exist_ok=True)
                    
                     yield tmp_path

# --- SCENARIOS ---

def test_wiring_cert_missing_skip(clean_env, mock_registry, mock_cert_registry):
    """Scenario 1: Sniper Cert Missing -> SKIP (via Defender/Judge)."""
    
    # Setup: Bundle exists but Certificate is CANDIDATE (Fail)
    mock_cert_registry.get_bundle_stage.return_value = STAGE_CANDIDATE
    
    # Patch BundleRegistry inside cloud_runtime to return our mock
    with patch("tezaver.matrix.bundles.bundle_registry.BundleRegistry", return_value=mock_registry):
        
        with patch("tezaver.matrix.pool.pool_engine_v1.build_universe_from_bundle_registry") as mock_univ:
             # Mock Universe Cell
             cell = PoolUniverseCellV1(
                 symbol="BTCUSDT",
                 timeframe="15m", 
                 bundles_loaded_ok=["BTC-15m-TEST"],
                 best_bundle_id="BTC-15m-TEST",
                 qc_score_best=90,
                 tier_best="GOLD"
             )
             cell.rank_score = 90
             mock_univ.return_value = [cell]
             
             # Execute
             res = pool_step(str(clean_env), "CLOUD_TEST", "WAR", {}, {})
             
             assert res["status"] == "OK", res.get("error")
             assert res["decision_action"] == "SKIP"
             assert res["verdict"] == "IMPROVE" 
             
             run_id = res["run_id"]
             report_path = clean_env / "war" / run_id / "reports" / "pool_intents_report_v1.json"
             with open(report_path) as f:
                 rep = json.load(f)
                 
             assert rep["intents_created"] == 0
             assert rep["skipped_reasons_count"].get("SKIPPED_NOT_CERTIFIED", 0) > 0

def test_wiring_risk_fail_block(clean_env, mock_registry, mock_cert_registry):
    """Scenario 2: Global Cap Exceeded -> BLOCK (via Prosecutor)."""
    
    # Setup: Cert PASSED
    mock_cert_registry.get_bundle_stage.return_value = STAGE_SNIPER_PASSED
    
    # Setup: Risk Limit very low
    risk_cfg = {"max_total_notional": 10.0} # Bundle wants 100
    
    with patch("tezaver.matrix.bundles.bundle_registry.BundleRegistry", return_value=mock_registry):
        with patch("tezaver.matrix.pool.pool_engine_v1.build_universe_from_bundle_registry") as mock_univ:
             cell = PoolUniverseCellV1(
                 symbol="BTCUSDT",
                 timeframe="15m", 
                 bundles_loaded_ok=["BTC-15m-TEST"],
                 best_bundle_id="BTC-15m-TEST",
                 qc_score_best=90,
                 tier_best="GOLD"
             )
             cell.rank_score = 90
             mock_univ.return_value = [cell]
             
             # Execute
             res = pool_step(str(clean_env), "CLOUD_TEST", "WAR", risk_cfg, {})
             
             assert res["status"] == "OK", res.get("error")
             assert res["decision_action"] == "BLOCK"
             assert res["verdict"] == "FAIL"
             
             run_id = res["run_id"]
             
             # Check Risk Report for reason
             risk_path = clean_env / "war" / run_id / "reports" / "pool_risk_report_v2.json"
             with open(risk_path) as f:
                 rep = json.load(f)
                 
             assert rep["blocked_count"] > 0
             assert rep["blocked_reasons_count"].get("GLOBAL_NOTIONAL_CAP", 0) > 0 # Fixed: GLOBAL_NOTIONAL_CAP matches code

def test_wiring_pass(clean_env, mock_registry, mock_cert_registry):
    """Scenario 3: All Good -> PASS."""
    
    # Setup: Cert PASSED
    mock_cert_registry.get_bundle_stage.return_value = STAGE_SNIPER_PASSED
    # Setup: High Limits
    risk_cfg = {"max_total_notional": 10000.0}
    
    with patch("tezaver.matrix.bundles.bundle_registry.BundleRegistry", return_value=mock_registry):
        with patch("tezaver.matrix.pool.pool_engine_v1.build_universe_from_bundle_registry") as mock_univ:
             cell = PoolUniverseCellV1(
                 symbol="BTCUSDT",
                 timeframe="15m", 
                 bundles_loaded_ok=["BTC-15m-TEST"],
                 best_bundle_id="BTC-15m-TEST",
                 qc_score_best=90,
                 tier_best="GOLD"
             )
             cell.rank_score = 90
             mock_univ.return_value = [cell]
             
             res = pool_step(str(clean_env), "CLOUD_TEST", "WAR", risk_cfg, {})
             
             assert res["status"] == "OK", res.get("error")
             
             if res["decision_action"] != "ALLOW":
                 # Debug: print verdict gates
                 run_id = res["run_id"]
                 v_path = clean_env / "war" / run_id / "reports" / "pool_court_verdict_v1.json"
                 if v_path.exists():
                     with open(v_path) as f:
                         print("VERDICT DUMP:", json.load(f))
             
             assert res["decision_action"] == "ALLOW"
             assert res["verdict"] == "PASS"

def test_wiring_idempotent_skip(clean_env, mock_registry, mock_cert_registry):
    """Scenario 4: Second run skips."""
    
    mock_cert_registry.get_bundle_stage.return_value = STAGE_SNIPER_PASSED
    risk_cfg = {"max_total_notional": 10000.0}
    
    with patch("tezaver.matrix.bundles.bundle_registry.BundleRegistry", return_value=mock_registry):
        with patch("tezaver.matrix.pool.pool_engine_v1.build_universe_from_bundle_registry") as mock_univ:
             cell = PoolUniverseCellV1(
                 symbol="BTCUSDT",
                 timeframe="15m", 
                 bundles_loaded_ok=["BTC-15m-TEST"],
                 best_bundle_id="BTC-15m-TEST",
                 qc_score_best=90,
                 tier_best="GOLD"
             )
             cell.rank_score = 90
             mock_univ.return_value = [cell]
             
             # Freeze time to ensure same ID
             with patch("time.time", return_value=1700001000.0): # 15m aligned? 1700001000 % 900 != 0
                  # 1700001000 / 900 = 1888890.0
                  # run_id uses last_closed_bar.
                  
                  # Run 1
                  res1 = pool_step(str(clean_env), "CLOUD_TEST", "WAR", risk_cfg, {})
                  assert res1["status"] == "OK", res1.get("error")
                  
                  # Run 2 (Same Ticks) 
                  res2 = pool_step(str(clean_env), "CLOUD_TEST", "WAR", risk_cfg, {})
                  assert res2["status"] == "SKIPPED_IDEMPOTENT"
                  assert res2["run_id"] == res1["run_id"]

