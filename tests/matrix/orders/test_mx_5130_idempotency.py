import pytest
from tezaver.matrix.orders.idempotency import IdempotencyManager

def test_idempotency_key_determinism():
    idem = IdempotencyManager("test_run")
    key1 = idem.build_key("BTCUSDT", "15m", "strat1", 1000, "OPEN", "LONG")
    key2 = idem.build_key("BTCUSDT", "15m", "strat1", 1000, "OPEN", "LONG")
    assert key1 == key2

def test_idempotency_blocking():
    idem = IdempotencyManager("test_run")
    key = idem.build_key("BTCUSDT", "15m", "strat1", 1000, "OPEN", "LONG")
    
    # First time: allowed
    assert idem.check_and_mark(key, {"order_id": "ord1"}) is True
    assert idem.blocked_count == 0
    
    # Second time: blocked
    assert idem.check_and_mark(key, {"order_id": "ord2"}) is False
    assert idem.blocked_count == 1

def test_idempotency_distinct_keys():
    idem = IdempotencyManager("test_run")
    key1 = idem.build_key("BTCUSDT", "15m", "strat1", 1000, "OPEN", "LONG")
    key2 = idem.build_key("ETHUSDT", "15m", "strat1", 1000, "OPEN", "LONG")
    
    assert idem.check_and_mark(key1, {"order_id": "ord1"}) is True
    assert idem.check_and_mark(key2, {"order_id": "ord2"}) is True
    assert idem.blocked_count == 0
