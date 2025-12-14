# Matrix V2 Coin Page Schema Test
"""
Tests for CoinStrategyPage schema and loader.
Covers both v1 (LEGACY) and v2 (CURRENT) schemas.
"""

import pytest
from pathlib import Path
import json
import tempfile


# =============================================================================
# V1 TESTS (LEGACY)
# =============================================================================

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


# =============================================================================
# V2 TESTS (CURRENT)
# =============================================================================

def test_coin_page_v2_schema_import():
    """Test that v2 schema types can be imported."""
    from tezaver.matrix.coin_page.schema import (
        CoinStrategyPageV2,
        TimeframeStrategiesV2,
        MatrixStrategyProfileV2,
        StrategyConfigV1,
        StrategyBenchmarkV1,
        StrategyRiskContractV1,
        StrategyRuntimeMode,
    )
    assert CoinStrategyPageV2 is not None
    assert TimeframeStrategiesV2 is not None
    assert MatrixStrategyProfileV2 is not None
    assert StrategyConfigV1 is not None
    assert StrategyBenchmarkV1 is not None
    assert StrategyRiskContractV1 is not None
    assert StrategyRuntimeMode is not None


def test_strategy_runtime_mode_default():
    """Test StrategyRuntimeMode default values."""
    from tezaver.matrix.coin_page.schema import StrategyRuntimeMode
    
    mode = StrategyRuntimeMode()
    assert mode.enabled is True


def test_strategy_benchmark_v1_instance():
    """Test creating StrategyBenchmarkV1."""
    from tezaver.matrix.coin_page.schema import StrategyBenchmarkV1
    
    benchmark = StrategyBenchmarkV1(
        capital_start=100.0,
        capital_end=100.57,
        pnl_pct=0.57,
        trades=7,
    )
    assert benchmark.capital_start == 100.0
    assert benchmark.capital_end == 100.57
    assert benchmark.pnl_pct == 0.57
    assert benchmark.trades == 7


def test_strategy_risk_contract_v1_instance():
    """Test creating StrategyRiskContractV1."""
    from tezaver.matrix.coin_page.schema import StrategyRiskContractV1
    
    contract = StrategyRiskContractV1(
        profile_kind="silver_15m",
        status="APPROVED",
        max_risk_per_trade=0.01,
        source="silver_15m_multi_coin_v1",
        notes="v1 uniform 1% risk cap",
        reference={"pnl_pct_ref": 0.57},
    )
    assert contract.profile_kind == "silver_15m"
    assert contract.status == "APPROVED"
    assert contract.max_risk_per_trade == 0.01


def test_strategy_config_v1_instance():
    """Test creating StrategyConfigV1."""
    from tezaver.matrix.coin_page.schema import StrategyConfigV1
    
    config = StrategyConfigV1(
        version="v2_ml",
        entry_filters={"rsi_15m": {"min": 20, "max": 30}},
        ml_filters={"rsi_gap_1d": {"min": -20, "max": 0}},
        exit={"tp_pct": 0.09, "sl_pct": 0.002, "max_horizon_bars": 48},
    )
    assert config.version == "v2_ml"
    assert config.exit["tp_pct"] == 0.09


def test_matrix_strategy_profile_v2_instance():
    """Test creating MatrixStrategyProfileV2."""
    from tezaver.matrix.coin_page.schema import (
        MatrixStrategyProfileV2,
        StrategyConfigV1,
        StrategyBenchmarkV1,
        StrategyRuntimeMode,
    )
    
    strategy = StrategyConfigV1(version="v2_ml")
    benchmark = StrategyBenchmarkV1(
        capital_start=100.0,
        capital_end=100.57,
        pnl_pct=0.57,
        trades=7,
    )
    
    profile = MatrixStrategyProfileV2(
        profile_id="BTC_SILVER_15M_CORE_V1",
        kind="silver_15m_core",
        status="APPROVED",
        strategy=strategy,
        benchmark_v1=benchmark,
    )
    
    assert profile.profile_id == "BTC_SILVER_15M_CORE_V1"
    assert profile.kind == "silver_15m_core"
    assert profile.status == "APPROVED"
    assert profile.runtime_mode.enabled is True


def test_coin_strategy_page_v2_instance():
    """Test creating CoinStrategyPageV2."""
    from tezaver.matrix.coin_page.schema import (
        CoinStrategyPageV2,
        TimeframeStrategiesV2,
        MatrixStrategyProfileV2,
        StrategyConfigV1,
    )
    
    strategy = StrategyConfigV1(version="v2_ml")
    profile = MatrixStrategyProfileV2(
        profile_id="BTC_SILVER_15M_CORE_V1",
        kind="silver_15m_core",
        status="APPROVED",
        strategy=strategy,
    )
    
    tf_strategies = TimeframeStrategiesV2(
        tf="15m",
        profiles={"BTC_SILVER_15M_CORE_V1": profile},
    )
    
    page = CoinStrategyPageV2(
        version="matrix_coin_page_v2",
        symbol="BTCUSDT",
        timeframes={"15m": tf_strategies},
    )
    
    assert page.version == "matrix_coin_page_v2"
    assert page.symbol == "BTCUSDT"
    assert "15m" in page.timeframes
    assert "BTC_SILVER_15M_CORE_V1" in page.timeframes["15m"].profiles


def test_coin_strategy_page_v2_loader():
    """Test loading CoinStrategyPageV2 from JSON."""
    from tezaver.matrix.coin_page.loader import load_coin_strategy_page_v2
    
    data = {
        "version": "matrix_coin_page_v2",
        "symbol": "BTCUSDT",
        "timeframes": {
            "15m": {
                "tf": "15m",
                "profiles": {
                    "BTC_SILVER_15M_CORE_V1": {
                        "profile_id": "BTC_SILVER_15M_CORE_V1",
                        "kind": "silver_15m_core",
                        "status": "APPROVED",
                        "strategy": {
                            "version": "v2_ml",
                            "entry_filters": {"rsi_15m": {"min": 20}},
                            "ml_filters": {},
                            "exit": {"tp_pct": 0.09},
                        },
                        "benchmark_v1": {
                            "capital_start": 100.0,
                            "capital_end": 100.57,
                            "pnl_pct": 0.57,
                            "trades": 7,
                        },
                        "risk_contract_v1": {
                            "profile_kind": "silver_15m",
                            "status": "APPROVED",
                            "max_risk_per_trade": 0.01,
                            "source": "silver_15m_multi_coin_v1",
                            "notes": "test",
                            "reference": {},
                        },
                        "runtime_mode": {"enabled": True},
                    }
                }
            }
        },
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = Path(f.name)
    
    try:
        page = load_coin_strategy_page_v2(temp_path)
        assert page.version == "matrix_coin_page_v2"
        assert page.symbol == "BTCUSDT"
        assert "15m" in page.timeframes
        
        profile = page.timeframes["15m"].profiles["BTC_SILVER_15M_CORE_V1"]
        assert profile.profile_id == "BTC_SILVER_15M_CORE_V1"
        assert profile.kind == "silver_15m_core"
        assert profile.status == "APPROVED"
        assert profile.strategy.version == "v2_ml"
        assert profile.benchmark_v1 is not None
        assert profile.benchmark_v1.pnl_pct == 0.57
        assert profile.risk_contract_v1 is not None
        assert profile.risk_contract_v1.max_risk_per_trade == 0.01
    finally:
        temp_path.unlink()


def test_coin_strategy_page_v2_loader_validation_wrong_version():
    """Test that v2 loader rejects wrong version."""
    from tezaver.matrix.coin_page.loader import load_coin_strategy_page_v2
    
    data = {
        "version": "1.0",  # Wrong version
        "symbol": "BTCUSDT",
        "timeframes": {"15m": {"tf": "15m", "profiles": {}}},
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = Path(f.name)
    
    try:
        with pytest.raises(ValueError, match="Unsupported coin page version"):
            load_coin_strategy_page_v2(temp_path)
    finally:
        temp_path.unlink()


def test_matrix_profile_repository_v2_loading():
    """Test MatrixProfileRepository loads from v2 when available."""
    from tezaver.matrix.core.profile import MatrixProfileRepository
    
    # Create v2 coin page
    data = {
        "version": "matrix_coin_page_v2",
        "symbol": "BTCUSDT",
        "timeframes": {
            "15m": {
                "tf": "15m",
                "profiles": {
                    "BTC_SILVER_15M_CORE_V1": {
                        "profile_id": "BTC_SILVER_15M_CORE_V1",
                        "kind": "silver_15m_core",
                        "status": "APPROVED",
                        "strategy": {
                            "version": "v2_ml",
                            "entry_filters": {},
                            "ml_filters": {},
                            "exit": {"tp_pct": 0.09},
                        },
                        "benchmark_v1": {
                            "capital_start": 100.0,
                            "capital_end": 100.57,
                            "pnl_pct": 0.57,
                            "trades": 7,
                        },
                        "runtime_mode": {"enabled": True},
                    }
                }
            }
        },
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coin_root = Path(tmpdir)
        symbol_dir = coin_root / "BTCUSDT"
        symbol_dir.mkdir()
        
        # Create v2 file
        coin_page_path = symbol_dir / "matrix_coin_page_v2.json"
        with open(coin_page_path, "w") as f:
            json.dump(data, f)
        
        # Test repository
        repo = MatrixProfileRepository(coin_root)
        profiles = repo.load_profiles_for_symbol("BTCUSDT")
        
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile.profile_id == "BTC_SILVER_15M_CORE_V1"
        assert profile.symbol == "BTCUSDT"
        assert profile.timeframe == "15m"
        assert profile.grade == "silver"  # Derived from kind
        assert profile.status == "APPROVED"
        
        # V2 fields should be populated
        assert profile.kind == "silver_15m_core"
        assert profile.strategy_config is not None
        assert profile.strategy_config.version == "v2_ml"
        assert profile.benchmark is not None
        assert profile.benchmark.pnl_pct == 0.57


def test_matrix_profile_repository_v2_fallback_to_v1():
    """Test MatrixProfileRepository falls back to v1 when v2 not present."""
    from tezaver.matrix.core.profile import MatrixProfileRepository
    
    # Create only v1 coin page (no v2)
    data_v1 = {
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
        },
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coin_root = Path(tmpdir)
        symbol_dir = coin_root / "BTCUSDT"
        symbol_dir.mkdir()
        
        # Create only v1 file
        coin_page_path = symbol_dir / "matrix_coin_page_v1.json"
        with open(coin_page_path, "w") as f:
            json.dump(data_v1, f)
        
        # Test repository falls back to v1
        repo = MatrixProfileRepository(coin_root)
        profiles = repo.load_profiles_for_symbol("BTCUSDT")
        
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile.profile_id == "BTC_SILVER_15M_CORE_V1"
        assert profile.grade == "silver"
        # V2 fields should be None (loaded from v1)
        assert profile.kind is None
        assert profile.strategy_config is None
        assert profile.benchmark is None

