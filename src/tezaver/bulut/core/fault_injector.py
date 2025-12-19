# Tezaver Bulut - Fault Injector Core
"""
Managed fault injection for controlled chaos engineering tests.
"""
import uuid
import json
import random
import asyncio
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class FaultTarget:
    """Target definition for a fault."""
    endpoint: str        # e.g. "POST /fapi/v1/order" or just "/fapi/v1/order"
    fault_type: str      # TIMEOUT, REJECT, ERROR_429, ERROR_500, PARTIAL_FILL
    count: int = 1       # How many times to inject (sequence)
    probability: float = 1.0 # 0.0 to 1.0
    params: Dict[str, Any] = field(default_factory=dict) # Extra params (e.g. latency_ms)

@dataclass
class FaultProfile:
    """A collection of fault targets."""
    id: str
    name: str
    description: str
    targets: List[FaultTarget]
    
    @classmethod
    def from_dict(cls, data: dict):
        targets = [FaultTarget(**t) for t in data.get("targets", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Unnamed Profile"),
            description=data.get("description", ""),
            targets=targets
        )

class FaultInjector:
    """
    Interceptor that can simulate faults.
    Designed to be plugged into Service Clients.
    """
    def __init__(self):
        self.profile: Optional[FaultProfile] = None
        self.counters: Dict[str, int] = {} # endpoint -> count of calls
        self.active_run_id: Optional[str] = None
        
    def load_profile(self, profile: FaultProfile, run_id: str = None):
        """Activate a profile."""
        self.profile = profile
        self.counters = {}
        self.active_run_id = run_id
        
    def clear(self):
        """Deactivate."""
        self.profile = None
        self.counters = {}
        self.active_run_id = None

    async def check_and_inject(self, method: str, url: str, **kwargs):
        """
        Check if current request matches any fault rule.
        If matched, perform the fault (raise Exception, sleep, return fake resp).
        
        Returns:
           None (proceed normally)
           Response object (if mocking response)
        
        Raises:
           Exception (TimeoutError, etc.) if fault dictates.
        """
        if not self.profile:
            return None
            
        # Simplified matching: check if endpoint is in url
        # "POST /fapi/v1/order"
        # We might just match partial string for now
        target_key = f"{method.upper()} {url}" 
        
        # Determine strict match or partial?
        # Let's iterate targets
        
        for target in self.profile.targets:
            # Check endpoint match
            # "POST /fapi/v1/order" in target.endpoint? OR target.endpoint in target_key?
            # Usually target.endpoint is substring of full URL
            # e.g. target="POST /fapi/v1/order"
            # Request might be "POST https://.../fapi/v1/order"
            
            # Extract path from URL?
            # Or just check if target.endpoint is in `method + " " + url`
            
            if target.endpoint in target_key or target.endpoint in url:
                # Match found. Check sequence/probability.
                
                # Check Probability
                if random.random() > target.probability:
                    continue
                    
                # Check Count (Sequence)
                key = f"{target_key}:{target.fault_type}"
                current_count = self.counters.get(key, 0)
                
                if current_count < target.count:
                    # Activate Fault
                    self.counters[key] = current_count + 1
                    return await self._execute_fault(target)
                    
        return None

    async def _execute_fault(self, target: FaultTarget):
        """Execute the specific fault logic."""
        ft = target.fault_type
        
        if ft == "TIMEOUT":
            # Simulate generic timeout (aiohttp format usually)
            raise asyncio.TimeoutError("Fault Injection: Simulated Timeout")
            
        elif ft == "REJECT":
            # Raise an APIError like 'Order Rejected'
            # We need to mock the specifics of the client's exception class if possible
            # Or return a response that allows client to parse it as error
            # If we raise generic Exception, client might treat as network error.
            # If REJECT usually means 200 OK with "status": "REJECTED" or 400 Bad Request?
            # Binance usually 400 with code -2010 or similar.
            # Let's return a Mock Response object with 400 status.
            return MockResponse(
                status=400,
                json_data={"code": -2010, "msg": "Simulated Filter Failure: LOT_SIZE"}
            )
            
        elif ft == "ERROR_429":
            return MockResponse(
                status=429,
                headers={"Retry-After": "5"},
                text="Too Many Requests"
            )
            
        elif ft == "ERROR_500":
            return MockResponse(status=500, text="Internal Server Error")
            
        elif ft == "PARTIAL_FILL":
            # This is tricky because PARTIAL FILL is logic inside response or subsequent WS stream?
            # For LIMIT order POST response, it is "NEW" or "PARTIALLY_FILLED" (IOC).
            # If we return a response with status "PARTIALLY_FILLED", system might handle it.
            # We need to construct a valid success response.
            return MockResponse(
                status=200,
                json_data={
                    "orderId": 123456789,
                    "symbol": "BTCUSDT",
                    "status": "PARTIALLY_FILLED",
                    "executedQty": "0.001",
                    "origQty": "0.01",
                    "price": "100000",
                    "avgPrice": "100000",
                    "cumQuote": "100",
                    "timeInForce": "GTC",
                    "type": "LIMIT",
                    "side": "BUY"
                }
            )
            
        return None


class MockResponse:
    """Mimic aiohttp ClientResponse."""
    def __init__(self, status: int, json_data: dict = None, text: str = "", headers: dict = None):
        self.status = status
        self._json = json_data or {}
        self._text = text
        self.headers = headers or {}
        
    async def json(self):
        return self._json
        
    async def text(self):
        return self._text
        
    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"Http Error {self.status}")
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc, tb):
        pass
