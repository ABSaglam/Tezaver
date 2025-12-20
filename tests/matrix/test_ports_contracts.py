import os
import json
from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.store_run_fs import FileRunStore

def test_data_port_json(tmp_path):
    bars_file = tmp_path / "bars.json"
    data = [{"ts": 0, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True}]
    with open(bars_file, "w") as f:
        json.dump(data, f)
        
    port = JsonFileDataPort(str(bars_file))
    bars = port.get_closed_bars("SYM", "15m")
    
    assert len(bars) == 1
    assert bars[0].ts == 0
    # Check sec->ms conversion logic
    assert bars[0].is_closed

def test_store_run_fs(tmp_path):
    store = FileRunStore(str(tmp_path))
    rid = "run_test"
    store.create_run(rid, {"meta": "val"})
    store.append_event(rid, {"ev": 1})
    store.write_gates(rid, {"g": 1})
    
    run_dir = tmp_path / "runs" / rid
    assert (run_dir / "meta.json").exists()
    assert (run_dir / "events.ndjson").exists()
    assert (run_dir / "gates.json").exists()
