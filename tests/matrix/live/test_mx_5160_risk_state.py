import pytest
from tezaver.matrix.live.risk_state import RiskStateManager, RiskMode

def test_risk_state_transitions():
    mgr = RiskStateManager("run123")
    assert mgr.mode == RiskMode.NORMAL
    
    mgr.enter_safe_mode("TEST_PRESSURE")
    assert mgr.mode == RiskMode.SAFE_MODE
    assert "TEST_PRESSURE" in mgr.reasons
    
    # HALTED should override SAFE_MODE
    mgr.enter_halted("CRITICAL_FAIL")
    assert mgr.mode == RiskMode.HALTED

def test_risk_order_enforcement():
    mgr = RiskStateManager("run123")
    
    # NORMAL: everything allowed
    can, _ = mgr.can_place_order("OPEN")
    assert can is True
    
    # SAFE_MODE: OPEN blocked, CLOSE allowed
    mgr.enter_safe_mode("GUARD_TRIPPED")
    can_open, reason = mgr.can_place_order("OPEN")
    assert can_open is False
    assert "OPEN_BLOCKED" in reason
    
    can_close, _ = mgr.can_place_order("CLOSE")
    assert can_close is True
    
    # HALTED: everything blocked
    mgr.enter_halted("KILL")
    can_open, _ = mgr.can_place_order("OPEN")
    assert can_open is False
    can_close, _ = mgr.can_place_order("CLOSE")
    assert can_close is False

def test_risk_recovery():
    mgr = RiskStateManager("run123")
    mgr.enter_safe_mode("R1")
    mgr.enter_safe_mode("R2")
    
    assert mgr.mode == RiskMode.SAFE_MODE
    
    mgr.recover("R1")
    assert mgr.mode == RiskMode.SAFE_MODE
    
    mgr.recover("R2")
    assert mgr.mode == RiskMode.NORMAL
