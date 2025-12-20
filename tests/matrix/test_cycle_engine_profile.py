from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.ports.broker_port import BrokerPort
from tezaver.matrix.adapters.store_run_fs import FileRunStore
import os
import json

class MockP(DataPort):
    def get_closed_bars(self, *args): return []
class MockB(BrokerPort):
    def place_order(self, *args): pass
    def cancel_order(self, *args): pass

def test_cycle_saves_profile(tmp_path):
    store = FileRunStore(str(tmp_path))
    trace = TraceIds("a","b","c")
    
    # Fake judge requirements
    drep = tmp_path / "data_reports"
    os.makedirs(drep)
    with open(drep / "latest.json","w") as f: json.dump({"ok":True},f)
    
    meta = run_cycle(
        "BTC", "1h", "2024", trace, MockP(), MockB(), store,
        RiskGateConfig(), GovernanceConfig(), str(tmp_path),
        run_profile="WAR"
    )
    
    assert meta["run_profile"] == "WAR"
    
    # Check disk
    rid = meta["run_id"]
    with open(tmp_path / "runs" / rid / "meta.json") as f:
        saved = json.load(f)
        assert saved["run_profile"] == "WAR"
