import pytest
from tezaver.matrix.core.config_signature import ConfigSpec, compute_config_signature

def test_config_signature_determinism():
    spec1 = ConfigSpec(
        run_profile="TEST", symbol="BTC", timeframe="1m", 
        risk={"a": 1, "b": 2}, governance={}, extras={}
    )
    # Order changed in dict
    spec2 = ConfigSpec(
        run_profile="TEST", symbol="BTC", timeframe="1m", 
        risk={"b": 2, "a": 1}, governance={}, extras={}
    )
    
    assert compute_config_signature(spec1) == compute_config_signature(spec2)
    assert len(compute_config_signature(spec1)) == 64 # SHA256 hex
