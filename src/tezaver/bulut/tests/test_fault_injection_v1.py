# Tezaver Bulut - Fault Injection Proof Tests
"""
Tests for Fault Injection mechanism covering P1 scenarios.
"""
import pytest
import asyncio
from tezaver.bulut.core.fault_injector import FaultInjector, FaultProfile, FaultTarget

# --- Mocks ---
class MockClient:
    def __init__(self, injector: FaultInjector):
        self.injector = injector
        
    async def post_order(self):
        # Hook injection
        fault_resp = await self.injector.check_and_inject("POST", "/fapi/v1/order")
        if fault_resp:
            return fault_resp
            
        return {"status": "REAL_SUCCESS", "orderId": 999}
        
    async def get_klines(self):
        fault_resp = await self.injector.check_and_inject("GET", "/fapi/v1/klines")
        if fault_resp:
            return fault_resp
        return [{"time": 1000, "close": 100}]

# --- Tests ---

@pytest.mark.asyncio
async def test_scenario_timeout_ambiguous():
    """Verify TIMEOUT injection works."""
    injector = FaultInjector()
    profile = FaultProfile(
        id="test_timeout", name="Timeout", description="",
        targets=[FaultTarget(endpoint="/fapi/v1/order", fault_type="TIMEOUT", count=1)]
    )
    injector.load_profile(profile, run_id="1")
    client = MockClient(injector)
    
    # 1st call -> Timeout
    with pytest.raises(asyncio.TimeoutError):
        await client.post_order()
        
    # 2nd call -> Success (count=1)
    res = await client.post_order()
    assert res["status"] == "REAL_SUCCESS"

@pytest.mark.asyncio
async def test_scenario_reject():
    """Verify REJECT injection."""
    injector = FaultInjector()
    profile = FaultProfile(
        id="test_reject", name="Reject", description="",
        targets=[FaultTarget(endpoint="/fapi/v1/order", fault_type="REJECT", count=1)]
    )
    injector.load_profile(profile)
    client = MockClient(injector)
    
    # Expect MockResponse with 400
    res = await client.post_order()
    assert res.status == 400
    json_data = await res.json()
    assert json_data["code"] == -2010

@pytest.mark.asyncio
async def test_scenario_429_rate_limit():
    """Verify 429 injection."""
    injector = FaultInjector()
    profile = FaultProfile(
        id="test_429", name="Rate Limit", description="",
        targets=[FaultTarget(endpoint="/fapi/v1/klines", fault_type="ERROR_429", count=1)]
    )
    injector.load_profile(profile)
    client = MockClient(injector)
    
    res = await client.get_klines()
    assert res.status == 429
    assert res.headers["Retry-After"] == "5"
    
    # Next call success
    res2 = await client.get_klines()
    assert isinstance(res2, list)

@pytest.mark.asyncio
async def test_scenario_partial_fill():
    """Verify PARTIAL_FILL injection."""
    injector = FaultInjector()
    profile = FaultProfile(
        id="test_partial", name="Partial", description="",
        targets=[FaultTarget(endpoint="/fapi/v1/order", fault_type="PARTIAL_FILL", count=1)]
    )
    injector.load_profile(profile)
    client = MockClient(injector)
    
    res = await client.post_order()
    # It returns a MockResponse with success 200 but status=PARTIALLY_FILLED
    assert res.status == 200
    data = await res.json()
    assert data["status"] == "PARTIALLY_FILLED"
    assert data["executedQty"] == "0.001"
