import pytest
import os
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore

def test_store_roundtrip(tmp_path):
    store = FileCandidateStore(home=str(tmp_path))
    
    data = {
        "symbol": "ETH",
        "timeframe": "1h",
        "bundle_version": "v1",
        "build_ts": "2025-01-01T12:00:00",
        "story": {
            "phases": [{"name": "SETUP", "start_bar": 10, "end_bar": 20}],
            "anchors": {"entry_bar": 18, "invalidation_bar": 5}
        }
    }
    
    cid = store.save(data)
    assert "ETH_1h_v1_2025_01_01T12_00_00" in cid
    
    loaded = store.load(cid)
    assert loaded["symbol"] == "ETH"
    
    ids = store.list_ids()
    assert cid in ids

def test_store_validate_on_save(tmp_path):
    store = FileCandidateStore(home=str(tmp_path))
    bad_data = {"symbol": "BTC"} # missing keys
    
    with pytest.raises(ValueError, match="Invalid bundle"):
        store.save(bad_data)
