import pytest
from unittest.mock import MagicMock
from tezaver.matrix.adapters.broker_binance_real import RealBinanceBroker
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

def test_broker_real_binance_uses_order_test_in_dryrun():
    client = MagicMock(spec=BinanceRestClient)
    
    # 1. Dry Run = True
    broker = RealBinanceBroker(client, dry_run=True)
    res = broker.place_order("S1", "BTCUSDT", "BUY", 1.0, 50000, 1000)
    
    client.order_test.assert_called_once()
    client.order_place.assert_not_called()
    assert res["accepted"]
    assert res["dryrun"]
    assert "TEST_" in res["order_id"]
    
    client.reset_mock()
    
    # 2. Dry Run = False (Real)
    broker_real = RealBinanceBroker(client, dry_run=False)
    client.order_place.return_value = {"orderId": 999, "clientOrderId": "cid"}
    
    res2 = broker_real.place_order("S1", "BTCUSDT", "SELL", 1.0, 50000, 1000)
    
    client.order_test.assert_not_called()
    client.order_place.assert_called_once()
    assert res2["accepted"]
    assert not res2["dryrun"]
    assert res2["order_id"] == "999"
    
    # Check reduceOnly for SELL
    call_args = client.order_place.call_args[0][0]
    assert call_args["reduceOnly"] == "true"
