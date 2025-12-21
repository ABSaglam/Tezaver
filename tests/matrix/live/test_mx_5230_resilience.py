import pytest
import time
import requests
from tezaver.matrix.live.api_resilience import ApiResilienceManager, ErrorClass, CircuitState

class FakeClient:
    def __init__(self):
        self.call_count = 0
        self.fail_until = 0
        self.fail_with = None

    def api_call(self):
        self.call_count += 1
        if self.call_count <= self.fail_until:
            if self.fail_with == "429":
                resp = requests.Response()
                resp.status_code = 429
                raise requests.exceptions.HTTPError(response=resp)
            elif self.fail_with == "TIMEOUT":
                raise requests.exceptions.Timeout("Connection timed out")
            else:
                raise Exception("Fatal error")
        return "SUCCESS"

def test_classify_429():
    manager = ApiResilienceManager("test")
    resp = requests.Response()
    resp.status_code = 429
    exc = requests.exceptions.HTTPError(response=resp)
    assert manager.classify_error(exc) == ErrorClass.RATE_LIMIT

def test_retry_transient_then_succeed():
    client = FakeClient()
    client.fail_until = 2
    client.fail_with = "TIMEOUT"
    
    manager = ApiResilienceManager("test", max_retries=3)
    # Monkeypatch sleep for speed
    import tezaver.matrix.live.api_resilience as ar
    ar.time.sleep = lambda x: None
    
    result = manager.call(client.api_call)
    assert result == "SUCCESS"
    assert client.call_count == 3
    assert manager.stats["retries_count"] == 2

def test_circuit_opens_on_repeated_fail():
    client = FakeClient()
    client.fail_until = 10
    client.fail_with = "FATAL"
    
    manager = ApiResilienceManager("test", circuit_threshold=2)
    
    with pytest.raises(Exception):
        manager.call(client.api_call)
    
    assert manager.failure_count == 1
    
    with pytest.raises(Exception):
        manager.call(client.api_call)
        
    assert manager.state == CircuitState.OPEN
    assert manager.stats["circuit_trips"] == 1

def test_circuit_blocks_while_open():
    manager = ApiResilienceManager("test")
    manager.state = CircuitState.OPEN
    manager.last_failure_ts = time.time()
    
    def dummy(): return "OK"
    
    with pytest.raises(Exception) as exc:
        manager.call(dummy)
    assert "CIRCUIT_BREAKER_OPEN" in str(exc.value)
