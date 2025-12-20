import pytest
import os
import json
import hashlib
from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.core.bars import Bar
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

def get_events_hash(run_dir):
    ndjson = os.path.join(run_dir, "events.ndjson")
    hasher = hashlib.sha256()
    with open(ndjson, "r") as f:
        for line in f:
            obj = json.loads(line)
            # Normalize: remove run_id which is variable
            obj.pop("run_id", None)
            # Dump sorted
            s = json.dumps(obj, sort_keys=True)
            hasher.update(s.encode("utf-8"))
    return hasher.hexdigest()

def test_cycle_determinism(tmp_path):
    bars = [Bar(i*1000, 10, 10, 10, 10, True) for i in range(5)]
    trace = TraceIds("v1", "fp", "sig")
    cand = {"symbol": "TEST"}
    risk = RiskGateConfig()
    gov = GovernanceConfig()
    
    # Run 1
    m1 = run_cycle(bars, trace, cand, risk, gov, str(tmp_path), "run1")
    h1 = get_events_hash(os.path.join(tmp_path, "runs", "run1"))
    
    # Run 2
    m2 = run_cycle(bars, trace, cand, risk, gov, str(tmp_path), "run2")
    h2 = get_events_hash(os.path.join(tmp_path, "runs", "run2"))
    
    assert h1 == h2
    assert m1['event_count'] == m2['event_count']
