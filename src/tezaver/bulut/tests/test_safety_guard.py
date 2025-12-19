# Tezaver Bulut - Safety Guard Tests
"""
Tests for Safety Guard blocking logic.
"""

import pytest
from unittest.mock import MagicMock
from tezaver.bulut.services.safety_guard import SafetyGuard


def test_guard_blocks_if_execution_disabled(cfg):
    """Test blocking when execution is disabled."""
    ctx = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.execution_enabled = False
    ctx.config = mock_cfg
    ctx.state = MagicMock()
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert not allowed
    assert reason == "EXECUTION_DISABLED"


def test_guard_blocks_if_arm_token_missing():
    """Test blocking when arm token required but missing."""
    ctx = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.execution_enabled = True
    mock_cfg.require_arm = True
    mock_cfg.arm_token = ""
    ctx.config = mock_cfg
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert not allowed
    assert reason == "ARM_TOKEN_MISSING"


def test_guard_allowed_if_all_ok():
    """Test allowed when all conditions pass."""
    ctx = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.execution_enabled = True
    mock_cfg.require_arm = True
    mock_cfg.arm_token = "SECRET"
    mock_cfg.mode = "REAL_TESTNET"
    mock_cfg.block_execution_if_time_sync_fail = False
    ctx.config = mock_cfg
    
    ctx.state = MagicMock()
    ctx.state.pattern_pack_loaded = True
    ctx.state.trade_locked = False
    
    ctx.time_sync = MagicMock()
    ctx.time_sync.is_healthy.return_value = (True, {})
    
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    assert allowed
    assert reason is None
