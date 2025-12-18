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

    async def create_listen_key(self) -> str:
        """Create a new User Data Stream ListenKey."""
        # POST /fapi/v1/listenKey (API Key only, no signature needed usually, but signed client handles header)
        # Actually Binance Futures User Data Stream documentation says: "API-key passed in the header".
        # _signed_request adds header. It signs params too, but here no params.
        # It handles error checking.
        # Note: listenKey endpoint requires API Key but NO signature.
        # However, _signed_request forces signature if we use it?
        # Let's check _signed_request. It appends signature.
        # We need a method for "API Key Only" request if strict.
        # Let's use `_request` directly if `_signed_request` is too strict.
        # But `_signed_request` is wrapper around `_request` that does signing.
        # We'll make a specialized method here to avoid modifying `_signed_request` complexity if possible.
        
        # Implementation using raw `_request` (we assume _request exists in base or here? No, this class inherits nothing? Wait, it has `_session`).
        # Ah, looking at imports/structure... this class uses `aiohttp` session?
        # The class does `_signed_request`. 
        # Let's implement `_apikey_request` or just call `_request` with header.
        # Wait, I don't see `_request` method in `BinanceFuturesSigned` viewing previous edits.
        # Ah, I haven't viewed the FULL file. I should verify if there is a generic helper.
        # I'll rely on `_signed_request` for now, assuming it works or I'll fix if it fails on signature.
        # Actually, Binance docs say: "POST /fapi/v1/listenKey ... endpoint requires the API Key."
        # It does NOT say "SIGNED".
        # Sending extra signature might be rejected.
        # I will check/do `_request` manually here.
        
        if not self._session:
            await self.create_session()

        url = f"{self._base_url}/fapi/v1/listenKey"
        headers = {"X-MBX-APIKEY": self._api_key}
        async with self._session.post(url, headers=headers) as resp:
            data = await resp.json()
            if resp.status != 200:
                # Assuming _telemetry is available or needs to be added/mocked
                # self._telemetry.emit("API_ERROR", {"endpoint": "create_listen_key", "status": resp.status, "msg": data.get("msg")})
                raise RuntimeError(f"Failed to create listenKey: {data}")
            return data["listenKey"]

    async def keepalive_listen_key(self) -> None:
        """Keepalive User Data Stream ListenKey."""
        # PUT /fapi/v1/listenKey
        if not self._session:
            await self.create_session()

        url = f"{self._base_url}/fapi/v1/listenKey"
        headers = {"X-MBX-APIKEY": self._api_key}
        async with self._session.put(url, headers=headers) as resp:
             if resp.status != 200:
                 data = await resp.json()
                 # Assuming _telemetry is available or needs to be added/mocked
                 # self._telemetry.emit("API_ERROR", {"endpoint": "keepalive_listen_key", "status": resp.status, "msg": data.get("msg")})
                 # Don't raise, just log. Caller handles reconnect loop.
                 print(f"[WARN] ListenKey keepalive failed: {data}")

    async def close_listen_key(self) -> None:
        """Close User Data Stream ListenKey."""
        # DELETE /fapi/v1/listenKey
        if not self._session:
            await self.create_session()

        url = f"{self._base_url}/fapi/v1/listenKey"
        headers = {"X-MBX-APIKEY": self._api_key}
        async with self._session.delete(url, headers=headers) as resp:
             # Just strict fire and forget
             pass

    async def get_user_trades(
        self, 
        symbol: str, 
        start_time: Optional[int] = None, 
        end_time: Optional[int] = None, 
        limit: int = 500
    ) -> List[Dict]:
        """Get trades for a specific account and symbol."""
        params = {"symbol": symbol, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
            
        return await self._request("GET", "/fapi/v1/userTrades", params)

    async def get_income_history(
        self,
        income_type: Optional[str] = None,
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000
    ) -> List[dict]:
        """
        Get income history (Funding Fees, etc).
        Weight: 30
        """
        params = {"limit": limit}
        if income_type:
            params["incomeType"] = income_type
        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
            
        return await self._get("/fapi/v1/income", params, signed=True)

    # --- Market Data (v0.19) ---

    async def get_book_ticker(self, symbol: str) -> dict:
        """
        Get best bid/ask for symbol.
        Weight: 2 (Single Symbol)
        """
        return await self._get("/fapi/v1/ticker/bookTicker", {"symbol": symbol}, signed=False)

    async def get_last_price(self, symbol: str) -> dict:
        """
        Get last price for symbol.
        Weight: 1
        """
        return await self._get("/fapi/v1/ticker/price", {"symbol": symbol}, signed=False)
