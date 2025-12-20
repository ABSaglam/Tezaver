import pytest
from unittest.mock import MagicMock, patch
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

def test_binance_client_builds_signed_request():
    client = BinanceRestClient("API_KEY", "API_SECRET", testnet=True)
    
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = {"id": 123}
        mock_req.return_value.headers = {}
        
        client.order_place({"symbol": "BTCUSDT", "quantity": 1})
        
        args, kwargs = mock_req.call_args
        method, url = args
        
        assert method == "POST"
        assert "order" in url
        
        headers = kwargs["headers"]
        assert headers["X-MBX-APIKEY"] == "API_KEY"
        
        params = kwargs["params"]
        # It's now a string query params
        assert isinstance(params, str)
        assert "signature=" in params
        assert "timestamp=" in params
        assert "symbol=BTCUSDT" in params
        assert "quantity=1" in params
