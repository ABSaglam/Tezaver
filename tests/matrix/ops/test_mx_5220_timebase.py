import pytest
import time
from tezaver.matrix.ops.timebase import now_iso, measure_skew, build_timebase_report

def test_timebase_iso_format():
    ts = now_iso()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z")

def test_measure_skew():
    # Mock server time to be 500ms ahead of local
    def mock_server_time():
        return int((time.time() + 0.5) * 1000)
    
    res = measure_skew(mock_server_time)
    assert "exchange_offset_ms" in res
    # Offset should be close to 500ms
    assert 400 < res["exchange_offset_ms"] < 600
    assert res["network_delay_ms"] >= 0

def test_build_report():
    skew = {"exchange_offset_ms": 50, "network_delay_ms": 10}
    report = build_timebase_report("run_test", skew)
    
    assert report["run_id"] == "run_test"
    assert report["monotonic_ok"] is True
    assert report["ok"] is True

def test_skew_out_of_sync():
    skew = {"exchange_offset_ms": 5000, "network_delay_ms": 10}
    report = build_timebase_report("run_fail", skew)
    assert report["ok"] is False # Skew too high
