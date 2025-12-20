import pytest
from tezaver.matrix.core.trace import TraceIds, require_trace_ids

def test_trace_ids_valid():
    t = TraceIds("v1", "fp1", "sig1")
    require_trace_ids(t) # Should not raise

def test_trace_ids_missing_engine():
    t = TraceIds("", "fp1", "sig1")
    with pytest.raises(ValueError, match="engine_version is missing"):
        require_trace_ids(t)

def test_trace_ids_missing_fingerprint():
    t = TraceIds("v1", "", "sig1")
    with pytest.raises(ValueError, match="data_fingerprint is missing"):
        require_trace_ids(t)
