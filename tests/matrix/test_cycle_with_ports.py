import pytest
import os
import json
from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore

def test_cycle_with_ports(tmp_path):
    # Setup Data
    bars_file = tmp_path / "bars.json"
    # Provide milliseconds here to test raw pass-through or sec conversion
    # JsonAdapter heuristic: ts < 1e11 => sec -> ms. 
    # Let's use sec (0, 900) to test conversion
    data_raw = [
        {"ts": 0, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True},
        {"ts": 900, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True}
    ]
    with open(bars_file, "w") as f:
        json.dump(data_raw, f)
        
    # Adapters
    data = JsonFileDataPort(str(bars_file))
    broker = SimBroker()
    store = FileRunStore(str(tmp_path))
    
    # Run
    meta = run_cycle(
        symbol="TEST",
        timeframe="15m",
        candidate_build_ts="2025-01-01",
        trace_ids=TraceIds("v4", "fp", "sig"),
        data=data,
        broker=broker,
        store=store,
        risk_cfg=RiskGateConfig(),
        gov_cfg=GovernanceConfig(),
        home=str(tmp_path),
        run_profile="SNIPER"
    )
    
    assert meta["event_count"] == 2
    
    run_dir = tmp_path / "runs" / meta["run_id"]
    assert (run_dir / "events.ndjson").exists()
