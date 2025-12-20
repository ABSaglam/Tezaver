import pytest
import os
import json
import time
from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.ports.broker_port import BrokerPort
from tezaver.matrix.adapters.store_run_fs import FileRunStore
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

class MockDataPort(DataPort):
    def get_closed_bars(self, *args): return [] # Empty bars for speed

class MockBrokerPort(BrokerPort):
    def place_order(self, *args): pass
    def cancel_order(self, *args): pass

def test_cycle_writes_artifacts(tmp_path):
    # Setup
    store = FileRunStore(str(tmp_path))
    trace = TraceIds("eng", "dat", "cfg")
    home = str(tmp_path)
    
    # Create fake data report for Judge logic
    drep = tmp_path / "data_reports"
    os.makedirs(drep)
    with open(drep / "latest.json", "w") as f:
        json.dump({"ok": True}, f)
    
    rid = "test_artifacts_run"
    
    meta = run_cycle(
        symbol="BTC", timeframe="1h", candidate_build_ts="2024",
        trace_ids=trace,
        data=MockDataPort(),
        broker=MockBrokerPort(),
        store=store,
        risk_cfg=RiskGateConfig(),
        gov_cfg=GovernanceConfig(),
        home=home,
        run_id=rid
    )
    
    # Verify artifacts exist
    run_dir = tmp_path / "runs" / rid
    assert (run_dir / "scorecard.json").exists()
    assert (run_dir / "judge.json").exists()
    
    # Verify candidate stage updated
    # Candidate ID constructed in engine: BTC_1h_v1_2024
    stg_dir = tmp_path / "candidates_stage" 
    assert stg_dir.exists()
    assert len(list(os.listdir(stg_dir))) > 0
