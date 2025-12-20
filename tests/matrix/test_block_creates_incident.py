import pytest
import os
import json
from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore

def test_cycle_block_incident(tmp_path):
    # Setup
    bars_file = tmp_path / "bars.json"
    with open(bars_file, "w") as f:
        json.dump([
             {"ts": 0, "open": 10, "high": 10, "low": 10, "close": 10, "is_closed": True}
        ], f)

    data = JsonFileDataPort(str(bars_file))
    broker = SimBroker()
    store = FileRunStore(str(tmp_path))
    
    # Force Block via Allowlist
    gov_cfg = GovernanceConfig(allowlist=["BTC"]) # We run "AVAX"
    
    meta = run_cycle(
        symbol="AVAX",
        timeframe="15m",
        candidate_build_ts="",
        trace_ids=TraceIds("v1", "fp", "sig"),
        data=data,
        broker=broker,
        store=store,
        risk_cfg=RiskGateConfig(),
        gov_cfg=gov_cfg,
        home=str(tmp_path)
    )
    
    # Check if blocked and incident created
    run_dir = tmp_path / "runs" / meta["run_id"]
    
    # Audit block logic:
    # Incident ID should be in meta? (Optional but helpful)
    assert meta.get("incident_id")
    iid = meta["incident_id"]
    
    assert (tmp_path / "incidents" / iid / "manifest.json").exists()
