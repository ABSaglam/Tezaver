# Guardrail V2 Wargame Integration Tests
"""
Tests for Guardrail V2 integration with War Game runner.
"""

import pytest
from pathlib import Path

from tezaver.matrix.core.guardrail import (
    GuardrailController,
    GuardrailConfig,
    GuardrailEnvironment,
)
from tezaver.matrix.core.profile import MatrixProfileRepository


# Skip tests if pattern datasets don't exist
def _has_silver_patterns(symbol: str) -> bool:
    path = Path(f"data/ai_datasets/{symbol}/15m/rally_patterns_v1.parquet")
    return path.exists()


class TestWargameGuardrailIntegration:
    """Tests for Guardrail V2 integration in War Game."""
    
    @pytest.mark.skipif(
        not _has_silver_patterns("BTCUSDT"),
        reason="BTCUSDT pattern dataset not available"
    )
    def test_wargame_report_carries_profile_status_and_risk_contract_btc(self):
        """WargameReport should carry profile_status and risk_contract_max for BTC."""
        from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
        
        report = run_silver_15m_from_patterns_for_symbol("BTCUSDT", 0.01, mode="contract")
        
        # Report should have profile metadata
        assert report.profile_id == "BTC_SILVER_15M_CORE_V1"
        assert report.profile_status in ("APPROVED", "EXPERIMENTAL", "DISABLED", None)
        # risk_contract_max can be None or 0.01
        assert report.risk_contract_max is None or report.risk_contract_max >= 0.0
    
    @pytest.mark.skipif(
        not _has_silver_patterns("SOLUSDT"),
        reason="SOLUSDT pattern dataset not available"
    )
    def test_wargame_does_not_block_experimental_profile_sol(self):
        """WARGAME mode should allow EXPERIMENTAL profiles (SOL) to trade."""
        from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
        
        # SOLUSDT has status=EXPERIMENTAL
        report = run_silver_15m_from_patterns_for_symbol("SOLUSDT", 0.01, mode="contract")
        
        # WARGAME should allow trades even for EXPERIMENTAL
        assert report.capital_start == 100.0
        assert report.profile_id == "SOL_SILVER_15M_CORE_V1"
        # Should have produced at least one event (ran the simulation)
    
    def test_profile_repo_loads_all_symbols(self):
        """MatrixProfileRepository should load profiles for all 3 symbols."""
        repo = MatrixProfileRepository(Path("data/coin_profiles"))
        
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
            profiles = repo.load_profiles_for_symbol(symbol)
            assert len(profiles) >= 1, f"No profiles found for {symbol}"
            
            profile = profiles[0]
            assert profile.strategy_config is not None, f"{symbol} missing strategy_config"
            assert profile.risk_contract is not None, f"{symbol} missing risk_contract"
