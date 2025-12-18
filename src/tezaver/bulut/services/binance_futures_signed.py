# Tezaver Bulut - Binance Futures Signed Client
"""
Async REST client for authenticated/signed Binance Futures endpoints.
"""

import aiohttp
import time
import hmac
import hashlib
from urllib.parse import urlencode
from typing import Dict, Any, Optional, List

from tezaver.bulut.core.config import BulutConfig


class BinanceFuturesSigned:
    """
    Authenticated Binance Client using HMAC-SHA256.
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
        self._base_url = (
            config.rest_base_url_testnet 
            if config.use_testnet 
            else config.rest_base_url
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._api_key = config.binance_api_key
        self._api_secret = config.binance_api_secret
    
    async def create_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
            
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
            
    def _sign(self, params: Dict[str, Any]) -> str:
        """Sign params with HMAC SHA256."""
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, endpoint: str, params: Dict[str, Any]) -> Dict:
        """Make signed request."""
        if not self._session:
            await self.create_session()
            
        if not self._api_key or not self._api_secret:
            raise ValueError("API Key/Secret missing")
            
        # Add timestamp
        params["timestamp"] = int(time.time() * 1000)
        
        # Sign
        signature = self._sign(params)
        params["signature"] = signature
        
        headers = {"X-MBX-APIKEY": self._api_key}
        url = f"{self._base_url}{endpoint}"
        
        # aiohttp params handling? 
        # For POST, Binance typically expects form-data or urlencoded body?
        # Actually Binance supports query-string style parameters even for POST usually, or mixed.
        # But safest is passing everything as params in URL for GET/DELETE,
        # and as query params for POST too according to some docs, OR body.
        # Binance fapi docs say parameters can be sent in query string or request body.
        # Let's settle on query string for simplicity as signature is on query string easily.
        
        try:
            async with self._session.request(method, url, params=params, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    return {"error": True, "status": resp.status, "msg": text}
                
                return await resp.json()
        except Exception as e:
            return {"error": True, "msg": str(e)}

    async def create_order(
        self, 
        symbol: str, 
        side: str, 
        qty: float, 
        order_type: str = "MARKET",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None
    ) -> Dict:
        """Create new order."""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": qty,
            "reduceOnly": "true" if reduce_only else "false"
        }
        if client_order_id:
            params["newClientOrderId"] = client_order_id
            
        return await self._request("POST", "/fapi/v1/order", params)
    
    async def place_stop_market_close_all(
        self,
        symbol: str,
        stop_price: float,
        client_order_id: str,
        working_type: str = "MARK_PRICE",
        price_protect: bool = True
    ) -> Dict:
        """Place STOP_MARKET close-all order."""
        params = {
            "symbol": symbol,
            "side": "SELL", # Long-only closure
            "type": "STOP_MARKET",
            "stopPrice": stop_price,
            "closePosition": "true", # Close-All
            "workingType": working_type,
            "priceProtect": "TRUE" if price_protect else "FALSE",
            "newClientOrderId": client_order_id
        }
        return await self._request("POST", "/fapi/v1/order", params)

    async def place_take_profit_market_close_all(
        self,
        symbol: str,
        stop_price: float, # Trigger price
        client_order_id: str,
        working_type: str = "MARK_PRICE",
        price_protect: bool = True
    ) -> Dict:
        """Place TAKE_PROFIT_MARKET close-all order."""
        params = {
            "symbol": symbol,
            "side": "SELL", # Long-only closure
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": stop_price,
            "closePosition": "true", # Close-All
            "workingType": working_type,
            "priceProtect": "TRUE" if price_protect else "FALSE",
            "newClientOrderId": client_order_id
        }
        return await self._request("POST", "/fapi/v1/order", params)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/fapi/v1/openOrders", params)

    async def cancel_order(self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None) -> Dict:
        """Cancel an order."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return await self._request("DELETE", "/fapi/v1/order", params)

    async def get_position_risk(self, symbol: Optional[str] = None) -> Any:
        """Get position risk."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/fapi/v2/positionRisk", params)

    async def get_open_orders(self, symbol: Optional[str] = None) -> Any:
        """Get open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/fapi/v1/openOrders", params)
