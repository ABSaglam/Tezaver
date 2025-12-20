import pytest
import os
import json
import hashlib
from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore

def get_events_hash(run_dir):
    ndjson = os.path.join(run_dir, "events.ndjson")
    hasher = hashlib.sha256()
    with open(ndjson, "r") as f:
        for line in f:
            obj = json.loads(line)
            obj.pop("run_id", None)
            s = json.dumps(obj, sort_keys=True)
            hasher.update(s.encode("utf-8"))
    return hasher.hexdigest()

def test_cycle_determinism(tmp_path):
    bars_file = tmp_path / "bars.json"
    with open(bars_file, "w") as f:
        json.dump([
             {"ts": i*900, "open": 10, "high": 10, "low": 10, "close": 10, "is_closed": True}
             for i in range(5)
        ], f)

    data = JsonFileDataPort(str(bars_file))
    broker = SimBroker()
    store = FileRunStore(str(tmp_path))
    
    args = dict(
        symbol="TEST",
        timeframe="15m",
        candidate_build_ts="",
        trace_ids=TraceIds("v1", "fp", "sig"),
        data=data,
        broker=broker,
        store=store,
        risk_cfg=RiskGateConfig(),
        gov_cfg=GovernanceConfig()
    )
    
    # Run 1
    m1 = run_cycle(**args, run_id="run1")
    h1 = get_events_hash(os.path.join(tmp_path, "runs", "run1"))
    
    # Run 2
    m2 = run_cycle(**args, run_id="run2")
    h2 = get_events_hash(os.path.join(tmp_path, "runs", "run2"))
    
    assert h1 == h2
    assert m1['event_count'] == m2['event_count']
