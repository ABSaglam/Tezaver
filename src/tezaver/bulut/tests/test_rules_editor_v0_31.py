import pytest
from unittest.mock import MagicMock, patch
from tezaver.bulut.services.rules_validator import RulesValidator
from tezaver.bulut.services.rules_registry import RulesRegistry

def test_validator_allowlist():
    val = RulesValidator.validate_allowlist("BTCUSDT\nETHUSDT # Comment")
    assert val["ok"]
    
    val_bad = RulesValidator.validate_allowlist("INVALID") # Need at least 2... chars per regex
    # Regex was ^[A-Z0-9]{2,25}$
    # "INVALID" is 7 chars. It should pass regex.
    assert val_bad["ok"]
    
    val_bad2 = RulesValidator.validate_allowlist("btc_usd") # lower, underscore not at start?
    # Regex [A-Z0-9] only.
    assert not val_bad2["ok"]

def test_validator_group_caps():
    val = RulesValidator.validate_group_caps({"A": 1, "B": 10})
    assert val["ok"]
    
    val_bad = RulesValidator.validate_group_caps({"A": -1})
    assert not val_bad["ok"]

@pytest.mark.asyncio
async def test_api_block_mainnet_armed():
    # Mock context to be Mainnet + Armed
    from tezaver.bulut.api.routes_rules import check_write_permission
    from fastapi import HTTPException
    
    ctx = MagicMock()
    ctx.config.mode = "REAL_MAINNET"
    ctx.config.rules_edit_enabled = True
    ctx.config.rules_edit_block_on_mainnet_armed = True
    ctx.execution_service.is_armed.return_value = True
    
    with pytest.raises(HTTPException) as exc:
        check_write_permission(ctx)
    assert exc.value.status_code == 409
    
    # Try DISARMED
    ctx.execution_service.is_armed.return_value = False
    # Should pass (no exception)
    check_write_permission(ctx)
