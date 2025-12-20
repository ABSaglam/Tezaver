import os
import json
import pytest
from tezaver.matrix.core.userstream_reconciler import reconcile_stream

def test_userstream_checkpoint_dedup(tmp_path):
    home = str(tmp_path)
    os.makedirs(tmp_path / "cloud_runtime" / "userstream", exist_ok=True)
    
    evt = {"e": "dummy"}
    with open(tmp_path / "cloud_runtime" / "userstream" / "raw.ndjson", "w") as f:
        f.write(json.dumps(evt) + "\n")
        
    # 1. First Pass
    res1 = reconcile_stream(home)
    assert res1["processed"] == 1
    
    # 2. Second Pass (No new data)
    res2 = reconcile_stream(home)
    assert res2["processed"] == 0
    
    # 3. Append
    with open(tmp_path / "cloud_runtime" / "userstream" / "raw.ndjson", "a") as f:
        f.write(json.dumps(evt) + "\n")
        
    # 4. Third Pass
    res3 = reconcile_stream(home)
    assert res3["processed"] == 1
