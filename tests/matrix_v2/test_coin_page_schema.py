# Matrix V2 Coin Page Schema Test
"""
Tests for CoinStrategyPage schema and loader.
"""

import pytest
from pathlib import Path
import json
import tempfile


def test_coin_page_schema_import():
    """Test that coin page schema can be imported."""
    from tezaver.matrix.coin_page.schema import (
        TimeframeProfile,
        TimeframeConfig,
        CoinStrategyPage,
    )
    assert TimeframeProfile is not None
    assert TimeframeConfig is not None
    assert CoinStrategyPage is not None


def test_timeframe_profile_instance():
    """Test creating a TimeframeProfile instance."""
    from tezaver.matrix.coin_page.schema import TimeframeProfile
    
    profile = TimeframeProfile(
        profile_id="btc_15m_gold_001",
        grade="gold",
        status="active",
        strategy_card="/path/to/card.json",
        matrix_role="scout",
    )
    assert profile.profile_id == "btc_15m_gold_001"
    assert profile.grade == "gold"
    assert profile.status == "active"


def test_coin_strategy_page_instance():
    """Test creating a CoinStrategyPage instance."""
    from tezaver.matrix.coin_page.schema import (
        TimeframeProfile,
        TimeframeConfig,
        CoinStrategyPage,
    )
    
    profile = TimeframeProfile(
        profile_id="btc_15m_silver_001",
        grade="silver",
        status="active",
        strategy_card="/path/to/card.json",
        matrix_role="trader",
    )
    
    config = TimeframeConfig(profiles=[profile])
    
    page = CoinStrategyPage(
        version="1.0",
        symbol="BTCUSDT",
        timeframes={"15m": config},
    )
    
    assert page.version == "1.0"
    assert page.symbol == "BTCUSDT"
    assert "15m" in page.timeframes
    assert len(page.timeframes["15m"].profiles) == 1


def test_coin_strategy_page_loader():
    """Test loading CoinStrategyPage from JSON."""
    from tezaver.matrix.coin_page.loader import load_coin_strategy_page
    
    data = {
        "version": "1.0",
        "symbol": "BTCUSDT",
        "timeframes": {
            "15m": {
                "profiles": [
                    {
                        "profile_id": "btc_15m_silver_001",
                        "grade": "silver",
                        "status": "active",
                        "strategy_card": "/path/to/card.json",
                        "matrix_role": "trader",
                    }
                ]
            }
        },
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = Path(f.name)
    
    try:
        page = load_coin_strategy_page(temp_path)
        assert page.version == "1.0"
        assert page.symbol == "BTCUSDT"
        assert "15m" in page.timeframes
    finally:
        temp_path.unlink()


def test_coin_strategy_page_loader_validation_errors():
    """Test that loader raises ValueError for invalid data."""
    from tezaver.matrix.coin_page.loader import load_coin_strategy_page
    
    # Missing version
    data_no_version = {"symbol": "BTCUSDT", "timeframes": {"15m": {"profiles": [{"profile_id": "x"}]}}}
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data_no_version, f)
        temp_path = Path(f.name)
    
    try:
        with pytest.raises(ValueError, match="version"):
            load_coin_strategy_page(temp_path)
    finally:
        temp_path.unlink()
    
    # Missing symbol
    data_no_symbol = {"version": "1.0", "timeframes": {"15m": {"profiles": [{"profile_id": "x"}]}}}
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data_no_symbol, f)
        temp_path = Path(f.name)
    
    try:
        with pytest.raises(ValueError, match="symbol"):
            load_coin_strategy_page(temp_path)
    finally:
        temp_path.unlink()


def test_matrix_profile_repository():
    """Test MatrixProfileRepository loading profiles from coin page."""
    from tezaver.matrix.core.profile import MatrixProfileRepository
    from pathlib import Path
    
    # Create temporary coin page
    data = {
        "version": "1.0",
        "symbol": "BTCUSDT",
        "timeframes": {
            "15m": {
                "profiles": [
                    {
                        "profile_id": "BTC_SILVER_15M_CORE_V1",
                        "grade": "silver",
                        "status": "APPROVED",
                        "strategy_card": "/path/to/card.json",
                        "matrix_role": "default",
                    }
                ]
            },
            "1h": {
                "profiles": [
                    {
                        "profile_id": "BTC_GOLD_1H_CORE_V1",
                        "grade": "gold",
                        "status": "EXPERIMENTAL",
                        "strategy_card": "/path/to/card2.json",
                        "matrix_role": "experimental",
                    }
                ]
            },
        },
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coin_root = Path(tmpdir)
        symbol_dir = coin_root / "BTCUSDT"
        symbol_dir.mkdir()
        
        coin_page_path = symbol_dir / "matrix_coin_page_v1.json"
        with open(coin_page_path, "w") as f:
            json.dump(data, f)
        
        # Test repository
        repo = MatrixProfileRepository(coin_root)
        profiles = repo.load_profiles_for_symbol("BTCUSDT")
        
        assert len(profiles) == 2
        assert profiles[0].profile_id == "BTC_SILVER_15M_CORE_V1"
        assert profiles[0].symbol == "BTCUSDT"
        assert profiles[0].timeframe == "15m"
        assert profiles[0].grade == "silver"
        assert profiles[0].status == "APPROVED"
        
        assert profiles[1].profile_id == "BTC_GOLD_1H_CORE_V1"
        assert profiles[1].timeframe == "1h"
        assert profiles[1].grade == "gold"
        assert profiles[1].status == "EXPERIMENTAL"
        
        # Test get_profile
        profile = repo.get_profile("BTC_SILVER_15M_CORE_V1")
        assert profile is not None
        assert profile.symbol == "BTCUSDT"
