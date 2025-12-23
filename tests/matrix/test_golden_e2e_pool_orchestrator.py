import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_loader_v1 import load_all_bundles
from tezaver.matrix.pool.pool_orchestrator_v1 import run_pool_evidence_bundle
from tezaver.matrix.pool_court.pool_court_runner_v1 import run_pool_court
from tezaver.matrix.pool_exec.pool_executor_sim_v0 import run_pool_execution_sim_v0
from tezaver.matrix.pool.portfolio_state_store_sim_v1 import load_state_v2
from tezaver.matrix.pool_exec.idempotency_store_v1 import keys_count

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def create_minimal_bundle(
    root_dir: Path,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    bundle_id: str = "golden_pool_bundle_001",
    qc_verdict: str = "PASS",
    qc_score: int = 88,
    notional: float = 100.0,
    exit_policy: str = "ATR"
) -> Path:
    """Create a minimal valid bundle (Phase 2A style)."""
    bundle_dir = root_dir / "approved_bundles_v1" / symbol / timeframe / "event_001"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "bundle_version": "approved_rally_bundle_v1",
        "bundle_id": bundle_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "event_id": "event_001",
        "event_time_iso": "2025-01-01T00:00:00",
        "approved": {
            "entry_bar_offset": 5,
            "entry_ts": "2025-01-01T01:00:00",
            "exit_bar_offset": 15,
            "exit_ts": None
        },
        "qc": {
            "verdict": qc_verdict,
            "score": qc_score
        },
        "tier": "GOLD",
        "trigger_spec_v1": {"type": "RALLY"},
        "policy_spec_v1": {
            "exit_policy": exit_policy,
            "notional": notional
        },
        "trace": {"created_by": "golden_e2e_test"}
    }
    
    with open(bundle_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Generic QC report
    qc_report = {"verdict": qc_verdict, "total_score": qc_score}
    with open(bundle_dir / "qc_report.json", 'w') as f:
        json.dump(qc_report, f, indent=2)
        
    return bundle_dir

@pytest.mark.golden_e2e
class TestGoldenE2EPoolOrchestrator:
    """
    Golden E2E: Full chain from bundles to execution simulation and idempotency.
    """
    
    @pytest.fixture(autouse=True)
    def setup_mock(self, tmp_path, monkeypatch):
        """Robustly mock resolve_reports_dir across all modules."""
        home = tmp_path
        def mock_resolve(s, r, h=None):
            return home / "out" / "matrix_runs" / s / r / "reports"
            
        monkeypatch.setattr("tezaver.matrix.pool.pool_reports_v1.resolve_reports_dir", mock_resolve)
        monkeypatch.setattr("tezaver.matrix.pool.pool_engine_v1.resolve_reports_dir", mock_resolve)
        monkeypatch.setattr("tezaver.matrix.pool.pool_orchestrator_v1.resolve_reports_dir", mock_resolve)
        monkeypatch.setattr("tezaver.matrix.pool_court.pool_court_runner_v1.resolve_reports_dir", mock_resolve)
        
        # Patch idempotency path
        monkeypatch.setattr("tezaver.matrix.pool_exec.idempotency_store_v1._get_store_path", 
                   lambda s, r, h=None: home / "out" / "matrix_runs" / s / r / "state" / "pool_idempotency_keys_v1.json")
        
        # Patch portfolio state path
        monkeypatch.setattr("tezaver.matrix.pool.portfolio_state_store_sim_v1.get_state_path",
                   lambda s, r, h=None: home / "out" / "matrix_runs" / s / r / "state" / "pool_portfolio_state_sim_v1.json")
        monkeypatch.setattr("tezaver.matrix.pool.portfolio_state_store_sim_v1.get_state_path_v2",
                   lambda s, r, h=None: home / "out" / "matrix_runs" / s / r / "state" / "pool_portfolio_state_sim_v2.json")

    def test_full_chain_happy_path_and_idempotency(self, tmp_path):
        home = tmp_path
        bundles_root = home / "approved_bundles_v1"
        create_minimal_bundle(home, bundle_id="B1", symbol="BTCUSDT")
        
        registry = BundleRegistry()
        load_all_bundles(str(bundles_root), registry)
        
        run_id = "golden_run_happy"
        stage = "war"
        trace_ctx = {"engine_version": "v1", "data_fingerprint": "DF", "config_signature": "CS"}
        
        # 1. Orchestrator
        options = {"closed_bars": {"15m": "2025-01-01T01:00:00"}}
        orch_res = run_pool_evidence_bundle(stage, run_id, trace_ctx, registry, options)
        assert orch_res["status"] == "OK"
        reports_dir = Path(orch_res["reports_dir"])
        
        # 2. Court
        court_res = run_pool_court(stage, run_id, trace_ctx, home_dir=str(home))
        if court_res["verdict"] != "PASS":
            with open(court_res["scorecard_path"]) as f:
                print(f"\n[DEBUG] Scorecard: {f.read()}")
        assert court_res["verdict"] == "PASS"
        
        # 3. Execution SIM
        exec_res = run_pool_execution_sim_v0(stage, run_id, trace_ctx, reports_dir)
        assert exec_res["sim_result"]["executed_sim"] == 1
        
        # 4. Idempotency (Run 2)
        exec_res_2 = run_pool_execution_sim_v0(stage, run_id, trace_ctx, reports_dir)
        assert exec_res_2["sim_result"]["executed_sim"] == 0
        assert exec_res_2["sim_result"]["skipped_idempotent"] == 1

    def test_risk_limiter_blocks_and_court_improves(self, tmp_path, monkeypatch):
        home = tmp_path
        bundles_root = home / "approved_bundles_v1"
        create_minimal_bundle(home, bundle_id="B_RISK", notional=100.0)
        
        registry = BundleRegistry()
        load_all_bundles(str(bundles_root), registry)
        
        # Use options to force global cap = 50.0
        run_id = "run_risk_block"
        options = {"global_limits": {"max_total_notional": 50.0}}
        
        orch_res = run_pool_evidence_bundle("war", run_id, {}, registry, options=options)
        reports_dir = Path(orch_res["reports_dir"])
        
        with open(reports_dir / "pool_risk_report_v2.json") as f:
            risk = json.load(f)
            assert risk["blocked_count"] == 1
            
        court_res = run_pool_court("war", run_id, {}, home_dir=str(home))
        assert court_res["verdict"] == "IMPROVE"

    def test_kill_switch_triggers_fail(self, tmp_path):
        home = tmp_path
        bundles_root = home / "approved_bundles_v1"
        create_minimal_bundle(home, bundle_id="B_KS")
        registry = BundleRegistry()
        load_all_bundles(str(bundles_root), registry)
        
        options = {"kill_switch_triggered": True}
        orch_res = run_pool_evidence_bundle("war", "run_ks", {}, registry, options=options)
        
        court_res = run_pool_court("war", "run_ks", {}, home_dir=str(home))
        assert court_res["verdict"] == "FAIL"
