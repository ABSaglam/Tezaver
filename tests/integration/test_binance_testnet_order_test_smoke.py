import os
import pytest
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

@pytest.mark.skipif(os.environ.get("TEZAVER_BINANCE_ITEST") != "1", reason="Requires TEZAVER_BINANCE_ITEST=1 and API keys")
def test_binance_testnet_order_test_smoke():
    # Requires ENV vars
    key = os.environ.get("TEZAVER_BINANCE_API_KEY")
    sec = os.environ.get("TEZAVER_BINANCE_API_SECRET")
    
    if not key or not sec:
        pytest.skip("Missing API Key/Secret for Integration Test")
        
    # Use Testnet
    client = BinanceRestClient(key, sec, testnet=True)
    
    # 1. Sync Time
    offset = client.sync_time()
    assert abs(offset) < 10000000 # Just sanity check, could be anything
    
    # 2. Public Ping
    # (Not exposed directly in client but via _request if needed, or just trust sync_time worked)
    
    # 3. Signed Order Test
    # Symbol: BTCUSDT often works on Futures Testnet
    res = client.order_test({
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "quantity": 0.001
    })
    
    # Should return empty dict {} or {"code": 0} on success
    # If error, it raises Exception
    assert isinstance(res, dict)
    
    print(f"Integration Test Success. Time Offset: {offset}ms")
