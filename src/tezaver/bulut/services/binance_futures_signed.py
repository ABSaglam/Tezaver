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
    
    def __init__(self, config: BulutConfig, governor=None, time_sync=None):
        self._config = config
        self._governor = governor
        self._time_sync = time_sync
        
        self._base_url = "https://fapi.binance.com"
        if config.use_testnet:
             self._base_url = "https://testnet.binancefuture.com"
             
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
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = True) -> Dict:
        """Internal helper for signed requests."""
        if params is None:
            params = {}

        if not self._session:
            await self.create_session()
            
        if not self._api_key:
            raise ValueError("API Key missing")

        # Governor
        if self._governor:
             # Construct config key e.g. "POST:/fapi/v1/order"
             key = f"{method}:{endpoint}"
             # Default to TRADE channel for signed ops
             await self._governor.acquire("TRADE", key)

        # Add timestamp
        if signed:
            # v0.13 Time Sync
            ts = int(time.time() * 1000)
            if self._time_sync:
                await self._time_sync.reload_if_due()
                ts = self._time_sync.now_ms()
                
            params["timestamp"] = ts
            # Default recvWindow from config if available, else 5000
            recv_win = getattr(self._config, "recv_window_ms", 5000)
            params["recvWindow"] = recv_win

            # Sign
            query_string = urlencode(params)
            signature = hmac.new(
                self._api_secret.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            
            url = f"{self._base_url}{endpoint}?{query_string}&signature={signature}"
        else:
            query_string = urlencode(params)
            url = f"{self._base_url}{endpoint}?{query_string}"
        
        headers = {"X-MBX-APIKEY": self._api_key}
        
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

    async def get_order_by_client_id(self, symbol: str, client_order_id: str) -> Dict:
        """Fetch a specific order by client ID (ambiguous resolution)."""
        params = {
            "symbol": symbol,
            "origClientOrderId": client_order_id
        }
        return await self._request("GET", "/fapi/v1/order", params)

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

    async def get_position_risk(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get position risk."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/fapi/v2/positionRisk", params)

    async def get_open_orders(self, symbol: Optional[str] = None) -> Any:
        """Get open orders."""
        params = {}
        return await self._request("GET", "/fapi/v1/openOrders", params)
