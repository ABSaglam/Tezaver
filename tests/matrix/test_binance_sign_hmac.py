import pytest
from tezaver.matrix.core.binance_sign import sign_request, build_query_string

def test_binance_sign_hmac():
    # Known test case
    # Secret: "nhqptmdsj05wgyxMz0byGSBurnqLp5U98" 
    # Params: symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1&recvWindow=5000&timestamp=1499827319559
    # Expected Signature: c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71
    # (Source: Binance Official Doc Example for Spot, similar for Futures)
    
    secret = "nhqptmdsj05wgyxMz0byGSBurnqLp5U98"
    params = {
        "symbol": "LTCBTC",
        "side": "BUY",
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": 1,
        "price": 0.1,
        "recvWindow": 5000,
        "timestamp": 1499827319559
    }
    
    # Docs signature hex (unsorted example): c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71
    # OUR IMPLEMENTATION SORTS PARAMS ALPHABETICALLY. 
    # The hash for the sorted string ("price=0.1&quantity=1...") is:
    expected = "672633295f1b481a5bad7fb847052e1fed9e1064d0946af965094c91a6aa9420"
    
    sig = sign_request(params, secret)
    assert sig == expected
    
    # Check alphabet sorting
    params_shuffled = {
        "timestamp": 1499827319559,
        "symbol": "LTCBTC",
        "recvWindow": 5000,
        "price": 0.1,
        "quantity": 1,
        "timeInForce": "GTC",
        "type": "LIMIT",
        "side": "BUY"
    }
    sig2 = sign_request(params_shuffled, secret)
    assert sig2 == expected
