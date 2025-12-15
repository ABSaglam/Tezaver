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
        max_wait_sec: float = 30.0,
        poll_interval_sec: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Fetch order details from Binance Futures Testnet.
        
        Optionally polls until FILLED or max_wait_sec.
        
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
        import time
        
        start_time = time.time()
        last_result = None
        
        while True:
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
                    executed_qty = float(data.get("executedQty", 0))
                    avg_price = float(data.get("avgPrice", 0))
                    
                    last_result = {
                        "orderId": str(data.get("orderId")),
                        "symbol": symbol,
                        "status": status,
                        "executedQty": executed_qty,
                        "avgPrice": avg_price,
                        "updateTime": data.get("updateTime"),
                        "side": data.get("side"),
                        "type": data.get("type"),
                        "success": True,
                        "error": None,
                    }
                    
                    # If FILLED or max_wait exceeded, return
                    if status == "FILLED":
                        return last_result
                    
                    elapsed = time.time() - start_time
                    if elapsed >= max_wait_sec:
                        return last_result
                    
                    # Poll again
                    time.sleep(poll_interval_sec)
                    continue
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

# =============================================================================
# Armed Executor (with dry-run and idempotency)
# =============================================================================

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
    ):
        self._exchange_mode = exchange_mode
        
        # Create appropriate gateway based on exchange_mode
        if gateway is not None:
            self._gateway = gateway
        elif exchange_mode == "REAL_TESTNET" and api_key and api_secret:
            self._gateway = BinanceTestnetGateway(api_key, api_secret)
        elif exchange_mode == "REAL_MAINNET":
            raise NotImplementedError("REAL_MAINNET gateway not implemented yet")
        else:
            self._gateway = DummyExchangeGateway()
        
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
        
        req = ExchangeOrderRequest(
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            tp_price=tp_price,
            sl_price=sl_price,
            # Clean client_id for Binance: only ^[.A-Z:/a-z0-9_-]{1,36}$ allowed
            client_id=fingerprint.replace("|", "_")[:36],
        )
        
        result = self._gateway.place_order(req)
        
        return ExecutionReport(
            success=result.success,
            dry_run=False,
            paused=False,
            duplicate=False,
            order_id=result.order_id,
            reason="GATEWAY_CALL",
            details={
                "action": action,
                "symbol": symbol,
                "qty": qty,
                "price": price,
                "filled_qty": result.filled_qty,
                "avg_price": result.avg_price,
                "fingerprint": fingerprint,
                "raw": result.raw,
            },
        )

