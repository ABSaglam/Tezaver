# Tezaver Bulut - Safety Guard Tests
"""
Tests for Safety Guard blocking logic.
"""

import pytest
from unittest.mock import MagicMock
from tezaver.bulut.services.safety_guard import SafetyGuard
from tezaver.bulut.core.config import BulutConfig

def test_guard_blocks_if_execution_disabled():
    ctx = MagicMock()
    ctx.config = BulutConfig(execution_enabled=False)
    ctx.state = MagicMock()
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert not allowed
    assert reason == "EXECUTION_DISABLED"

def test_guard_blocks_if_arm_token_missing():
    ctx = MagicMock()
    ctx.config = BulutConfig(execution_enabled=True, require_arm=True, arm_token="")
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert not allowed
    assert reason == "ARM_TOKEN_MISSING"

def test_guard_allowed_if_all_ok():
    ctx = MagicMock()
    ctx.config = BulutConfig(
        execution_enabled=True, 
        require_arm=True, 
        arm_token="SECRET",
        mode="REAL_TESTNET"
    )
    ctx.state = MagicMock()
    ctx.state.pattern_pack_loaded = True
    ctx.state.trade_locked = False
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert allowed
    assert reason is None
