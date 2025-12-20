# Matrix Live Gateway
"""
Exchange gateway interface and dummy implementation.

This module defines the interface for communicating with real exchanges.
Currently provides only a dummy implementation for development/testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Dict, Any


class OrderSide(str, Enum):
    """Order side: BUY or SELL."""
    BUY = "BUY"
    SELL = "SELL"


class ExchangeMode(str, Enum):
    """Exchange execution mode."""
    DRY_RUN = "DRY_RUN"  # No order submission, dry_run=True
    DUMMY_ORDER = "DUMMY_ORDER"  # Fake order ID, pipeline test
    REAL_TESTNET = "REAL_TESTNET"  # Binance testnet (requires secrets)
    REAL_MAINNET = "REAL_MAINNET"  # Production (requires secrets)


@dataclass
class ExchangeOrderRequest:
    """Request to place an order on the exchange."""
    symbol: str
    side: OrderSide
    quantity: float
    # Price fields are optional (market order by default)
    price: Optional[float] = None
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    client_id: Optional[str] = None
    reduce_only: bool = False  # For closing positions
    extra: Optional[Dict[str, Any]] = None  # Exchange-specific fields


@dataclass
class ExchangeOrderResult:
    """Result of an order placement attempt."""
    success: bool
    symbol: str
    side: OrderSide
    requested_qty: float
    filled_qty: float
    avg_price: Optional[float]
    order_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class IExchangeGateway(Protocol):
    """
    Abstract interface for exchange communication.
    
    Important: This interface does NOT handle API keys/secrets.
    It only defines the contract that Tezaver Matrix expects.
    Real implementations can be in separate projects/services.
    """

    def place_order(self, req: ExchangeOrderRequest) -> ExchangeOrderResult:
        """Place an order on the exchange."""
        ...

    def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Fetch order status."""
        ...

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        ...

    def get_position_snapshot(self, symbol: str) -> Dict[str, Any]:
        """
        Get position/margin snapshot for a symbol.
        
        Example return:
        {
          "symbol": "BTCUSDT",
          "position_qty": 0.01,
          "entry_price": 42000.0,
          "unrealized_pnl": 12.5,
        }
        """
        ...
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance snapshot.
        
        Returns:
            {
                "equity": float,
                "available": float,
                "used_margin": float,
                "unrealized_pnl": float,
                "source": str,  # "dummy", "binance-testnet", etc.
            }
        """
        ...
    
    def get_open_orders(self, symbol: str = None) -> list:
        """
        Get open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns list of order dicts:
            [{
                "orderId": str,
                "symbol": str,
                "side": str,
                "type": str,
                "quantity": float,
                "price": float,
                "status": str,
            }]
        """
        ...


class DummyExchangeGateway:
    """
    Development/demo gateway.
    
    - Does NOT make real HTTP calls.
    - Accepts all orders as "successful".
    - Uses fixed price=1.0 if no price is provided.
    - Tracks virtual positions for DRY_RUN testing.
    """
    
    def __init__(self):
        self._virtual_positions: Dict[str, Dict[str, Any]] = {}

    def place_order(self, req: ExchangeOrderRequest) -> ExchangeOrderResult:
        """Simulate placing an order (always succeeds)."""
        filled_price = req.price if req.price is not None else 1.0
        
        # Update virtual position
        if req.side == "BUY":
            self._virtual_positions[req.symbol] = {
                "position_qty": req.quantity,
                "entry_price": filled_price,
            }
        elif req.side == "SELL":
            self._virtual_positions[req.symbol] = {
                "position_qty": 0.0,
                "entry_price": None,
            }
        
        return ExchangeOrderResult(
            success=True,
            symbol=req.symbol,
            side=req.side,
            requested_qty=req.quantity,
            filled_qty=req.quantity,
            avg_price=filled_price,
            order_id="DUMMY-ORDER",
            raw={"note": "DummyExchangeGateway used"},
        )

    def get_position_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Return virtual position snapshot."""
        pos = self._virtual_positions.get(symbol, {})
        return {
            "symbol": symbol,
            "position_qty": pos.get("position_qty", 0.0),
            "entry_price": pos.get("entry_price"),
            "unrealized_pnl": 0.0,
            "note": "DummyExchangeGateway virtual position",
        }

    def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Dummy get_order: always returns FILLED immediately."""
        # For Dummy, we assume it was a BUY for 1.0 logic or track it properly.
        # Ideally we'd store orders in a dict. But since this is dummy, let's use a trick
        # or just assume 0.002 (common test size) if not found.
        # Better: Since place_order is called first, let's just return what we have.
        
        # NOTE: In a real dummy impl we would store orders.
        # Here we just want to satisfy the interface.
        return {
            "orderId": order_id,
            "symbol": symbol,
            "status": "FILLED",
            "executedQty": 0.002,  # Hardcoded valid-ish qty for testing
            "avgPrice": 42000.0,
            "updateTime": 1234567890,
            "side": "BUY",
            "type": "MARKET",
            "success": True,
        }

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Dummy cancel_order."""
        return {
            "orderId": order_id,
            "symbol": symbol,
            "status": "CANCELED",
            "success": True,
        }
    
    def get_balance(self) -> Dict[str, Any]:
        """Return dummy balance."""
        return {
            "equity": 0.0,
            "available": 0.0,
            "used_margin": 0.0,
            "unrealized_pnl": 0.0,
            "source": "dummy",
        }
    
    def get_open_orders(self, symbol: str = None) -> list:
        """Return empty orders list."""
        return []


class BinanceTestnetGateway:
    """
    Binance Testnet Gateway for REAL_TESTNET mode.
    
    - Makes real HTTP calls to Binance Futures Testnet.
    - Requires API_KEY and API_SECRET.
    - Uses HMAC-SHA256 signed requests.
    
    Testnet URL: https://testnet.binancefuture.com
    """
    
    TESTNET_BASE_URL = "https://testnet.binancefuture.com"
    
    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize with API credentials.
        
        WARNING: Never log api_key or api_secret!
        """
        self._api_key = api_key
        self._api_secret = api_secret
    
    def _sign_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp and signature to request params."""
        import time
        import hmac
        import hashlib
        import urllib.parse
        
        params["timestamp"] = int(time.time() * 1000)
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params
    
    def place_order(self, req: ExchangeOrderRequest) -> ExchangeOrderResult:
        """Place a market order on Binance Futures Testnet."""
        import requests
        
        try:
            # Build order params
            params = {
                "symbol": req.symbol,
                "side": req.side.value,
                "type": "MARKET",
                "quantity": req.quantity,
            }
            
            # Add reduceOnly for closing positions
            if req.reduce_only:
                params["reduceOnly"] = "true"
            
            if req.client_id:
                params["newClientOrderId"] = req.client_id[:36]  # Max 36 chars
            
            # Sign the request
            signed_params = self._sign_request(params)
            
            # Make the request
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v1/order"
            
            response = requests.post(url, params=signed_params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return ExchangeOrderResult(
                    success=True,
                    symbol=req.symbol,
                    side=req.side,
                    requested_qty=req.quantity,
                    filled_qty=float(data.get("executedQty", 0)),
                    avg_price=float(data.get("avgPrice", 0)) if data.get("avgPrice") else None,
                    order_id=str(data.get("orderId", "UNKNOWN")),
                    raw=data,
                )
            else:
                return ExchangeOrderResult(
                    success=False,
                    symbol=req.symbol,
                    side=req.side,
                    requested_qty=req.quantity,
                    filled_qty=0,
                    avg_price=None,
                    order_id=None,
                    error=data.get("msg", f"HTTP {response.status_code}"),
                    raw=data,
                )
        
        except Exception as e:
            return ExchangeOrderResult(
                success=False,
                symbol=req.symbol,
                side=req.side,
                requested_qty=req.quantity,
                filled_qty=0,
                avg_price=None,
                order_id=None,
                error=str(e),
            )
    
    def get_position_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get position snapshot from Binance Futures Testnet."""
        import requests
        
        try:
            params = self._sign_request({})
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v2/positionRisk"
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                for pos in data:
                    if pos.get("symbol") == symbol:
                        return {
                            "symbol": symbol,
                            "position_qty": float(pos.get("positionAmt", 0)),
                            "entry_price": float(pos.get("entryPrice", 0)) if pos.get("entryPrice") else None,
                            "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                        }
            
            return {
                "symbol": symbol,
                "position_qty": 0.0,
                "entry_price": None,
                "unrealized_pnl": 0.0,
            }
        
        except Exception as e:
            return {
                "symbol": symbol,
                "position_qty": 0.0,
                "entry_price": None,
                "unrealized_pnl": 0.0,
                "error": str(e),
            }
    
    def get_order(
        self,
        symbol: str,
        order_id: str,
    ) -> Dict[str, Any]:
        """
        Fetch order details from Binance Futures Testnet.
        
        Returns:
            {
                "orderId": str,
                "symbol": str,
                "status": str,  # NEW, PARTIALLY_FILLED, FILLED, CANCELED, etc.
                "executedQty": float,
                "avgPrice": float,
                "updateTime": int,
                "side": str,
                "type": str,
                "success": bool,
                "error": str or None,
            }
        """
        import requests
        
        try:
            params = {
                "symbol": symbol,
                "orderId": order_id,
            }
            signed_params = self._sign_request(params)
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v1/order"
            
            response = requests.get(url, params=signed_params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                status = data.get("status", "UNKNOWN")
                return {
                    "orderId": str(data.get("orderId")),
                    "symbol": symbol,
                    "status": status,
                    "executedQty": float(data.get("executedQty", 0)),
                    "avgPrice": float(data.get("avgPrice", 0)),
                    "updateTime": data.get("updateTime"),
                    "side": data.get("side"),
                    "type": data.get("type"),
                    "success": True,
                    "error": None,
                }
            else:
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "status": "ERROR",
                    "executedQty": 0,
                    "avgPrice": 0,
                    "updateTime": None,
                    "side": None,
                    "type": None,
                    "success": False,
                    "error": data.get("msg", f"HTTP {response.status_code}"),
                }
                
        except Exception as e:
            return {
                "orderId": order_id,
                "symbol": symbol,
                "status": "ERROR",
                "executedQty": 0,
                "avgPrice": 0,
                "updateTime": None,
                "side": None,
                "type": None,
                "success": False,
                "error": str(e),
            }

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel order on Binance Futures Testnet."""
        import requests
        
        try:
            params = {
                "symbol": symbol,
                "orderId": order_id,
            }
            signed_params = self._sign_request(params)
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v1/order"
            
            response = requests.delete(url, params=signed_params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return {
                    "orderId": str(data.get("orderId")),
                    "symbol": symbol,
                    "status": data.get("status"),
                    "success": True,
                    "error": None,
                }
            else:
                return {
                    "orderId": order_id,
                    "symbol": symbol,
                    "status": "ERROR",
                    "success": False,
                    "error": data.get("msg", f"HTTP {response.status_code}"),
                }
        except Exception as e:
             return {
                "orderId": order_id,
                "symbol": symbol,
                "status": "ERROR",
                "success": False,
                "error": str(e),
            }
    
    def get_user_trades(
        self,
        symbol: str,
        order_id: str,
    ) -> Dict[str, Any]:
        """
        Fetch trades for a specific order to get commission/fee.
        
        Uses /fapi/v1/userTrades with orderId filter.
        
        Returns:
            {
                "trades": List[dict],
                "total_qty": float,
                "total_commission": float,
                "commission_asset": str,
                "success": bool,
                "error": str or None,
            }
        """
        import requests
        
        try:
            params = {
                "symbol": symbol,
                "orderId": order_id,
            }
            signed_params = self._sign_request(params)
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v1/userTrades"
            
            response = requests.get(url, params=signed_params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and isinstance(data, list):
                total_qty = sum(float(t.get("qty", 0)) for t in data)
                total_commission = sum(float(t.get("commission", 0)) for t in data)
                commission_asset = data[0].get("commissionAsset", "USDT") if data else "USDT"
                
                return {
                    "trades": data,
                    "total_qty": total_qty,
                    "total_commission": total_commission,
                    "commission_asset": commission_asset,
                    "success": True,
                    "error": None,
                }
            else:
                return {
                    "trades": [],
                    "total_qty": 0,
                    "total_commission": 0,
                    "commission_asset": "USDT",
                    "success": False,
                    "error": data.get("msg", f"HTTP {response.status_code}") if isinstance(data, dict) else f"HTTP {response.status_code}",
                }
                
        except Exception as e:
            return {
                "trades": [],
                "total_qty": 0,
                "total_commission": 0,
                "commission_asset": "USDT",
                "success": False,
                "error": str(e),
            }
    
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance from Binance Futures Testnet."""
        import requests
        
        try:
            params = self._sign_request({})
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v2/account"
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200:
                return {
                    "equity": float(data.get("totalWalletBalance", 0)),
                    "available": float(data.get("availableBalance", 0)),
                    "used_margin": float(data.get("totalMarginBalance", 0)) - float(data.get("availableBalance", 0)),
                    "unrealized_pnl": float(data.get("totalUnrealizedProfit", 0)),
                    "source": "binance-testnet",
                }
            else:
                return {
                    "equity": 0.0,
                    "available": 0.0,
                    "used_margin": 0.0,
                    "unrealized_pnl": 0.0,
                    "source": "binance-testnet",
                    "error": data.get("msg", f"HTTP {response.status_code}"),
                }
        except Exception as e:
            return {
                "equity": 0.0,
                "available": 0.0,
                "used_margin": 0.0,
                "unrealized_pnl": 0.0,
                "source": "binance-testnet",
                "error": str(e),
            }
    
    def get_open_orders(self, symbol: str = None) -> list:
        """Get open orders from Binance Futures Testnet."""
        import requests
        
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol
            signed_params = self._sign_request(params)
            headers = {"X-MBX-APIKEY": self._api_key}
            url = f"{self.TESTNET_BASE_URL}/fapi/v1/openOrders"
            
            response = requests.get(url, params=signed_params, headers=headers, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and isinstance(data, list):
                return [{
                    "orderId": str(o.get("orderId", "")),
                    "symbol": o.get("symbol", ""),
                    "side": o.get("side", ""),
                    "type": o.get("type", ""),
                    "quantity": float(o.get("origQty", 0)),
                    "price": float(o.get("price", 0)),
                    "status": o.get("status", ""),
                } for o in data]
            else:
                return []
        except Exception:
            return []

# =============================================================================
# Fault Injection Gateway
# =============================================================================

class FaultInjectionGateway:
    """
    Wrapper gateway that injects faults into get_order flow.
    
    Fault Modes:
    - NONE: Pass through (default)
    - TIMEOUT: get_order never returns FILLED (loops forever or raises Timeout)
    - REJECT: get_order returns REJECTED status
    - PARTIAL: get_order returns PARTIALLY_FILLED then FILLED
    """
    
    def __init__(
        self,
        inner: IExchangeGateway,
        fault_mode: str = "NONE",
        fault_on_nth: int = 0,  # 0=all orders, N=only fault Nth order
        fault_action: str = "ANY",  # ANY/OPEN/CLOSE
    ):
        self._inner = inner
        self._fault_mode = fault_mode
        self._fault_on_nth = fault_on_nth
        self._fault_action = fault_action
        self._call_counts: Dict[str, int] = {}  # order_id -> count
        self._order_counter = 0  # Global order counter for nth-order fault
        self._order_sides: Dict[str, str] = {}  # order_id -> side (BUY/SELL)
        self._order_numbers: Dict[str, int] = {}  # order_id -> order number (1, 2, ...)
        self._order_actions: Dict[str, str] = {}  # order_id -> action (OPEN/CLOSE) based on side
        
    def place_order(self, req: ExchangeOrderRequest) -> ExchangeOrderResult:
        res = self._inner.place_order(req)
        if res.success and res.order_id:
            self._order_counter += 1
            self._order_sides[str(res.order_id)] = req.side.value
            self._order_numbers[str(res.order_id)] = self._order_counter
            # Infer action: BUY = OPEN, SELL = CLOSE (for long-only strategy)
            action = "OPEN" if req.side.value == "BUY" else "CLOSE"
            self._order_actions[str(res.order_id)] = action
        return res
        
    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        return self._inner.cancel_order(symbol, order_id)
        
    def get_position_snapshot(self, symbol: str) -> Dict[str, Any]:
        return self._inner.get_position_snapshot(symbol)

    def get_user_trades(self, symbol: str, order_id: str) -> Dict[str, Any]:
        if hasattr(self._inner, "get_user_trades"):
            return self._inner.get_user_trades(symbol, order_id)
        return {"success": False, "error": "Not supported"}

    def get_balance(self) -> Dict[str, Any]:
        """Pass-through balance check."""
        if hasattr(self._inner, "get_balance"):
            return self._inner.get_balance()
        return {}

    def get_open_orders(self, symbol: str = None) -> list:
        """Pass-through open orders check."""
        if hasattr(self._inner, "get_open_orders"):
            return self._inner.get_open_orders(symbol)
        return []

    def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Intercept get_order to inject faults."""
        if self._fault_mode == "NONE":
            return self._inner.get_order(symbol, order_id)
            
        real_res = self._inner.get_order(symbol, order_id)
        
        # Determine side (if we tracked it, else peek real_res if avail)
        side = self._order_sides.get(str(order_id)) or real_res.get("side")
        
        # Track calls for this order
        count = self._call_counts.get(order_id, 0) + 1
        self._call_counts[order_id] = count
        
        # Mode-specific Logic
        should_fail = False
        
        # Check if this is the Nth order we should fault
        order_num = self._order_numbers.get(str(order_id), 0)
        skip_fault = (self._fault_on_nth > 0 and order_num != self._fault_on_nth)
        
        # Check if action matches fault_action filter
        order_action = self._order_actions.get(str(order_id), "UNKNOWN")
        if self._fault_action != "ANY" and order_action != self._fault_action:
            skip_fault = True
        
        if skip_fault:
            # Not the target order - pass through without fault
            return real_res
        
        if self._fault_mode == "TIMEOUT":
            should_fail = True
        elif self._fault_mode == "TIMEOUT_OPEN" and side == "BUY":
            should_fail = True
        elif self._fault_mode == "TIMEOUT_CLOSE" and side == "SELL":
            should_fail = True
            
        if should_fail:
            # Simulate silence: return NEW forever
            return {
                **real_res,
                "status": "NEW",
                "executedQty": 0.0,
            }
            
        elif self._fault_mode == "REJECT":
            return {
                **real_res,
                "status": "REJECTED",
                "executedQty": 0.0,
                "error": "Simulated Rejection",
            }
            
        elif self._fault_mode == "PARTIAL":
            # Simulate partial fill flow
            full_qty = float(real_res.get("executedQty", 1.0))
            if full_qty == 0: 
                full_qty = 1.0 
            
            # Request A: executed_qty=orig_qty*0.5, avg_price=mock_price
            mock_price = float(real_res.get("avgPrice", 42000.0))
            if mock_price == 0: mock_price = 42000.0
                
            if count <= 2:
                # First 2 calls: 50% fill
                return {
                    **real_res,
                    "status": "PARTIALLY_FILLED",
                    "executedQty": full_qty * 0.5,
                    "avgPrice": mock_price,
                }
            else:
                # Then full fill
                return {
                    **real_res,
                    "status": "FILLED",
                    "executedQty": full_qty,
                    "avgPrice": mock_price,
                }
        
        return real_res


@dataclass
class ExecutionReport:
    """Result of execution attempt."""
    success: bool
    dry_run: bool
    paused: bool
    duplicate: bool
    order_id: Optional[str] = None
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ArmedExecutor:
    """
    Armed executor with dry-run mode and idempotency.
    
    - armed=False: DRY_RUN mode (no real orders)
    - armed=True: Real gateway execution
    - Duplicate fingerprint guard
    - Per-cell pause support
    - Fingerprint persistence for restart durability
    """
    
    def __init__(
        self,
        gateway: IExchangeGateway = None,
        armed: bool = False,
        exchange_enabled: bool = False,
        event_sink: Optional[callable] = None,
        exchange_mode: str = "DRY_RUN",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        # Lifecycle config
        poll_interval_sec: float = 2.0,
        order_timeout_sec: float = 30.0,
        cancel_on_timeout: bool = False,
        inject_fault: str = "NONE",
    ):
        self._exchange_mode = exchange_mode
        self._poll_interval = poll_interval_sec
        self._order_timeout = order_timeout_sec
        self._cancel_on_timeout = cancel_on_timeout
        
        # Create appropriate gateway based on exchange_mode
        base_gateway = None
        if gateway is not None:
            base_gateway = gateway
        elif exchange_mode == "REAL_TESTNET" and api_key and api_secret:
            base_gateway = BinanceTestnetGateway(api_key, api_secret)
        elif exchange_mode == "REAL_MAINNET":
            raise NotImplementedError("REAL_MAINNET gateway not implemented yet")
        else:
            base_gateway = DummyExchangeGateway()
            
        # Wrap with Fault Injection if needed
        if inject_fault and inject_fault != "NONE":
            self._gateway = FaultInjectionGateway(base_gateway, inject_fault)
        else:
            self._gateway = base_gateway
        
        self._armed = armed
        self._exchange_enabled = exchange_enabled
        self._event_sink = event_sink
        self._order_fingerprints: Dict[str, str] = {}  # cell_key -> last fingerprint
        self._paused_cells: Dict[str, bool] = {}  # cell_key -> paused
        self._global_paused: bool = False
    
    def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit event to sink (if configured)."""
        if self._event_sink:
            from datetime import datetime, timezone
            if "ts" not in event:
                event["ts"] = datetime.now(timezone.utc).isoformat()
            self._event_sink(event)
    
    @property
    def armed(self) -> bool:
        return self._armed
    
    @property
    def exchange_enabled(self) -> bool:
        return self._exchange_enabled
    
    def set_armed(self, armed: bool) -> None:
        """Set armed mode."""
        self._armed = armed
    
    def set_exchange_enabled(self, enabled: bool) -> None:
        """Set exchange enabled flag."""
        self._exchange_enabled = enabled
    
    def set_global_paused(self, paused: bool) -> None:
        """Set global pause."""
        self._global_paused = paused
    
    def set_cell_paused(self, cell_key: str, paused: bool) -> None:
        """Set per-cell pause."""
        self._paused_cells[cell_key] = paused
    
    def is_paused(self, cell_key: str) -> bool:
        """Check if cell is paused."""
        return self._global_paused or self._paused_cells.get(cell_key, False)
    
    # =========================================================================
    # Fingerprint Persistence
    # =========================================================================
    
    def save_fingerprints(self, path: str) -> None:
        """Save fingerprints to file for restart durability."""
        import json
        from pathlib import Path
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._order_fingerprints, f)
    
    def load_fingerprints(self, path: str) -> None:
        """Load fingerprints from file."""
        import json
        from pathlib import Path
        
        if Path(path).exists():
            with open(path) as f:
                self._order_fingerprints = json.load(f)
    
    def get_fingerprints(self) -> Dict[str, str]:
        """Get current fingerprints dict."""
        return self._order_fingerprints.copy()
    
    def _make_fingerprint(
        self,
        symbol: str,
        timeframe: str,
        profile_id: str,
        action: str,
        qty: float,
        tick_index: int,
        decision_ts: str,
    ) -> str:
        """Create order fingerprint for idempotency."""
        return f"{symbol}|{timeframe}|{profile_id}|{action}|{qty}|{tick_index}|{decision_ts}"
    
    def execute(
        self,
        symbol: str,
        timeframe: str,
        profile_id: str,
        action: str,
        qty: float,
        price: Optional[float] = None,
        tick_index: int = 0,
        decision_ts: str = "",
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
    ) -> ExecutionReport:
        """
        Execute order with armed/dry-run logic.
        
        Returns ExecutionReport with success, dry_run, paused, duplicate flags.
        """
        cell_key = f"{symbol}|{timeframe}|{profile_id}"
        
        # Check pause
        if self.is_paused(cell_key):
            return ExecutionReport(
                success=False,
                dry_run=not self._armed,
                paused=True,
                duplicate=False,
                reason="CELL_PAUSED",
                details={"cell_key": cell_key, "global_paused": self._global_paused},
            )
        
        # Check exchange_enabled (blocks real orders even if armed)
        if self._armed and not self._exchange_enabled:
            return ExecutionReport(
                success=False,
                dry_run=True,
                paused=False,
                duplicate=False,
                reason="EXCHANGE_DISABLED",
                details={"armed": True, "exchange_enabled": False},
            )
        
        # Check duplicate
        fingerprint = self._make_fingerprint(
            symbol, timeframe, profile_id, action, qty, tick_index, decision_ts
        )
        
        if cell_key in self._order_fingerprints:
            if self._order_fingerprints[cell_key] == fingerprint:
                return ExecutionReport(
                    success=False,
                    dry_run=not self._armed,
                    paused=False,
                    duplicate=True,
                    reason="DUPLICATE_ORDER",
                    details={"fingerprint": fingerprint},
                )
        
        # Record fingerprint
        self._order_fingerprints[cell_key] = fingerprint
        
        # Emit ORDER_SUBMIT (before execution)
        self._emit_event({
            "event_type": "ORDER_SUBMIT",
            "symbol": symbol,
            "timeframe": timeframe,
            "profile_id": profile_id,
            "exchange_mode": "DRY_RUN" if not self._armed else "ARMED",
            "exec_mode": "dry_run" if not self._armed else "live",
            "armed": self._armed,
            "exchange_enabled": self._exchange_enabled,
            "order_id": "DRY_RUN" if not self._armed else "PENDING",
            "fingerprint": fingerprint,
            "request_meta": {"type": "MARKET", "side": action.upper()},
        })
        
        # Dry run mode
        if not self._armed:
            result = ExecutionReport(
                success=True,
                dry_run=True,
                paused=False,
                duplicate=False,
                order_id="DRY_RUN",
                reason="DRY_RUN_MODE",
                details={
                    "action": action,
                    "symbol": symbol,
                    "qty": qty,
                    "price": price,
                    "fingerprint": fingerprint,
                },
            )
            
            # Emit ORDER_RESULT
            self._emit_event({
                "event_type": "ORDER_RESULT",
                "symbol": symbol,
                "timeframe": timeframe,
                "profile_id": profile_id,
                "exec_mode": "dry_run",
                "order_id": "DRY_RUN",
                "success": True,
                "duplicate": False,
                "paused": False,
                "reason": "DRY_RUN_MODE",
                "fingerprint": fingerprint,
                "exchange_mode": "DRY_RUN",
                "armed": False,
                "exchange_enabled": self._exchange_enabled,
            })
            
            return result
        
        # Armed mode - real gateway call
        side = OrderSide.BUY if action.upper() in ("BUY", "LONG", "ENTER") else OrderSide.SELL
        
        # Generate safe Client Order ID from fingerprint hash
        # Use simple hash to keep it short and alphanumeric for Binance
        import hashlib
        fp_hash = hashlib.md5(fingerprint.encode()).hexdigest()[:16]
        client_order_id = f"teza_{fp_hash}"
        
        req = ExchangeOrderRequest(
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            tp_price=tp_price,
            sl_price=sl_price,
            client_id=client_order_id,
        )
        
        # 1. Submit Order
        try:
            submit_res = self._gateway.place_order(req)
        except Exception as e:
             return ExecutionReport(
                success=False,
                dry_run=False,
                paused=False,
                duplicate=False,
                reason="SUBMIT_EXCEPTION",
                details={"error": str(e), "fingerprint": fingerprint},
            )

        if not submit_res.success:
            return ExecutionReport(
                success=False,
                dry_run=False,
                paused=False,
                duplicate=False,
                reason="SUBMIT_FAILED",
                details={
                    "error": submit_res.error,
                    "fingerprint": fingerprint,
                    "raw": submit_res.raw
                },
            )
            
        # 2. Track Lifecycle (Poll until terminal)
        from tezaver.matrix.live.order_lifecycle import OrderLifecycleTracker, OrderLifecycleState
        
        tracker = OrderLifecycleTracker(
            gateway=self._gateway,
            symbol=symbol,
            order_id=submit_res.order_id,
            client_order_id=client_order_id,
            poll_interval_sec=self._poll_interval,
            max_wait_sec=self._order_timeout,
            cancel_on_timeout=self._cancel_on_timeout,
            event_sink=self._event_sink,
        )
        
        lifecycle_res = tracker.poll_until_terminal()
        
        # 3. Construct Final Execution Report
        return ExecutionReport(
            success=lifecycle_res.is_success,
            dry_run=False,
            paused=False,
            duplicate=False,
            order_id=submit_res.order_id,
            reason="LIFECYCLE_DONE" if lifecycle_res.is_success else f"LIFECYCLE_{lifecycle_res.terminal_state.value}",
            details={
                "action": action,
                "symbol": symbol,
                "qty": qty,
                "price": price,
                "filled_qty": lifecycle_res.executed_qty,
                "avg_price": lifecycle_res.avg_price,
                "fingerprint": fingerprint,
                "client_order_id": client_order_id,
                "terminal_state": lifecycle_res.terminal_state.value,
                "attempts": lifecycle_res.attempts,
                "duration_ms": lifecycle_res.duration_ms,
                "error": lifecycle_res.error,
            },
        )

