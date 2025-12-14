# Guardrail V2 Tests – Profile Awareness
"""
Tests for profile-aware guardrail decisions.
"""

import pytest
from tezaver.matrix.core.guardrail import (
    GuardrailController,
    GuardrailConfig,
    GuardrailContext,
    GuardrailEnvironment,
)
from tezaver.matrix.core.profile import MatrixCellProfile
from tezaver.matrix.coin_page.schema import StrategyRiskContractV1


def _make_profile(status: str, max_risk: float = 0.01) -> MatrixCellProfile:
    """Create a minimal test profile with given status and risk contract."""
    profile = MatrixCellProfile(
        profile_id="TEST_PROFILE",
        symbol="BTCUSDT",
        timeframe="15m",
        grade="silver",
        status=status,
        strategy_card_path="",
        matrix_role="default",
        metadata={},
        kind="silver_15m_core",
        strategy_config=None,
        benchmark=None,
        risk_contract=StrategyRiskContractV1(
            profile_kind="silver_15m",
            status=status,
            max_risk_per_trade=max_risk,
            source="test",
            notes="Test contract",
            reference={},
        ),
        runtime_mode=None,
    )
    return profile


class TestGuardrailProfileAwareness:
    """Tests for check_profile_and_risk method."""
    
    def test_live_blocks_disabled_profile(self):
        """LIVE mode should block DISABLED profiles."""
        ctrl = GuardrailController(GuardrailConfig())
        profile = _make_profile("DISABLED")
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST_PROFILE",
            environment=GuardrailEnvironment.LIVE,
            risk_per_trade_requested=1.0,
        )
        dec = ctrl.check_profile_and_risk(profile, ctx)
        
        assert dec.allow is False
        assert dec.reason_code == "PROFILE_DISABLED"
        assert dec.profile_status == "DISABLED"
    
    def test_live_blocks_experimental_profile(self):
        """LIVE mode should block EXPERIMENTAL profiles."""
        ctrl = GuardrailController(GuardrailConfig())
        profile = _make_profile("EXPERIMENTAL")
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST_PROFILE",
            environment=GuardrailEnvironment.LIVE,
            risk_per_trade_requested=1.0,
        )
        dec = ctrl.check_profile_and_risk(profile, ctx)
        
        assert dec.allow is False
        assert dec.reason_code == "PROFILE_EXPERIMENTAL_WARGAME_ONLY"
        assert dec.profile_status == "EXPERIMENTAL"
    
    def test_live_allows_approved_profile(self):
        """LIVE mode should allow APPROVED profiles."""
        ctrl = GuardrailController(GuardrailConfig())
        profile = _make_profile("APPROVED")
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST_PROFILE",
            environment=GuardrailEnvironment.LIVE,
            risk_per_trade_requested=0.01,
        )
        dec = ctrl.check_profile_and_risk(profile, ctx)
        
        assert dec.allow is True
        assert dec.reason_code == "OK"
        assert dec.profile_status == "APPROVED"
        assert dec.risk_contract_max == 0.01
    
    def test_wargame_allows_experimental_profile(self):
        """WARGAME mode should allow EXPERIMENTAL profiles."""
        ctrl = GuardrailController(GuardrailConfig())
        profile = _make_profile("EXPERIMENTAL")
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST_PROFILE",
            environment=GuardrailEnvironment.WARGAME,
            risk_per_trade_requested=1.0,
        )
        dec = ctrl.check_profile_and_risk(profile, ctx)
        
        assert dec.allow is True
        assert dec.reason_code == "OK"
        assert dec.profile_status == "EXPERIMENTAL"
    
    def test_wargame_allows_disabled_profile(self):
        """WARGAME mode should allow even DISABLED profiles."""
        ctrl = GuardrailController(GuardrailConfig())
        profile = _make_profile("DISABLED")
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST_PROFILE",
            environment=GuardrailEnvironment.WARGAME,
            risk_per_trade_requested=1.0,
        )
        dec = ctrl.check_profile_and_risk(profile, ctx)
        
        assert dec.allow is True
        assert dec.reason_code == "OK"
        assert dec.profile_status == "DISABLED"
    
    def test_profile_not_found_allows_with_warning(self):
        """Missing profile should allow (fail-open) with warning reason."""
        ctrl = GuardrailController(GuardrailConfig())
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="UNKNOWN_PROFILE",
            environment=GuardrailEnvironment.LIVE,
            risk_per_trade_requested=1.0,
        )
        dec = ctrl.check_profile_and_risk(None, ctx)
        
        assert dec.allow is True
        assert dec.reason_code == "PROFILE_NOT_FOUND"
        assert dec.profile_status == "UNKNOWN"
        assert dec.risk_contract_max is None
    
    def test_risk_contract_max_extracted(self):
        """Decision should carry risk_contract_max from profile."""
        ctrl = GuardrailController(GuardrailConfig())
        profile = _make_profile("APPROVED", max_risk=0.02)
        ctx = GuardrailContext(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST_PROFILE",
            environment=GuardrailEnvironment.WARGAME,
        )
        dec = ctrl.check_profile_and_risk(profile, ctx)
        
        assert dec.risk_contract_max == 0.02
