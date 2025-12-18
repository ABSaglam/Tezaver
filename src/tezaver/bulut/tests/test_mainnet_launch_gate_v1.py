import pytest
import time
from unittest.mock import MagicMock
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.services.safety_guard import SafetyGuard
from tezaver.bulut.services.launch_checklist import LaunchChecklist

def test_mainnet_blocks_without_allowlist():
    # Setup
    cfg = BulutConfig(
        mode="REAL_MAINNET",
        require_allowlist_on_mainnet=True,
        mainnet_require_checklist_pass=False # focus on allowlist check first
    )
    
    # Mock Context
    ctx = MagicMock(spec=BulutContext)
    ctx.config = cfg
    ctx.state.startup_degraded = False
    ctx.state.pattern_pack_loaded = True
    
    # Mock Allowlist Source (empty)
    ctx.allowlist_source.get_allowlist_count.return_value = 0
    
    guard = SafetyGuard()
    
    # Check
    locked, reason = guard.check_trade_lock(ctx)
    assert locked is True
    assert reason == "MAINNET_ALLOWLIST_MISSING"
    
    # Mock Allowlist populated
    ctx.allowlist_source.get_allowlist_count.return_value = 5
    locked, reason = guard.check_trade_lock(ctx)
    assert locked is False

def test_mainnet_checklist_gate():
    cfg = BulutConfig(
        mode="REAL_MAINNET",
        require_allowlist_on_mainnet=False,
        mainnet_require_checklist_pass=True,
        checklist_max_age_seconds=10
    )
    ctx = MagicMock(spec=BulutContext)
    ctx.config = cfg
    ctx.state.startup_degraded = False
    ctx.state.pattern_pack_loaded = True
    
    checklist = LaunchChecklist(cfg, MagicMock())
    ctx.launch_checklist = checklist
    
    guard = SafetyGuard()
    
    # 1. Not Run yet
    locked, reason = guard.check_trade_lock(ctx)
    assert locked is True
    assert reason == "CHECKLIST_NOT_PASSING"
    
    # 2. Run Fail
    # Can't easily mock internal run logic without mocks inside checklist service.
    # But we can inject last result if we mocked the service methods.
    # Actually ctx.launch_checklist is a real object here (or mocked above?)
    # I assigned real object.
    # I can mock `get_last_result`.
    
    checklist.get_last_result = MagicMock(return_value={"pass": False, "ts": time.time()})
    locked, reason = guard.check_trade_lock(ctx)
    assert locked is True
    assert reason == "CHECKLIST_NOT_PASSING"
    
    # 3. Run Pass but Stale
    checklist.get_last_result = MagicMock(return_value={"pass": True, "ts": time.time() - 20})
    locked, reason = guard.check_trade_lock(ctx)
    assert locked is True
    assert reason == "CHECKLIST_STALE"
    
    # 4. Pass and Fresh
    checklist.get_last_result = MagicMock(return_value={"pass": True, "ts": time.time()})
    locked, reason = guard.check_trade_lock(ctx)
    assert locked is False
