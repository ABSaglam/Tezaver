# Tezaver Bulut - Idempotency Tests
"""
Tests for idempotency service.
"""

from tezaver.bulut.services.idempotency import IdempotencyService

def test_idempotency_format():
    key = "test_key_123"
    client_id = IdempotencyService.make_client_order_id(key)
    
    assert client_id.startswith("tb_")
    assert len(client_id) <= 36
    # Deterministic
    assert client_id == IdempotencyService.make_client_order_id(key)
    
    # Different keys
    client_id2 = IdempotencyService.make_client_order_id("test_key_124")
    assert client_id != client_id2
