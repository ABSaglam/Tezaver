# Matrix V2 Live Module
"""
Live trading components for Matrix v2.
"""

from pathlib import Path

from .live_config import MatrixLiveConfig, LiveStrategyCellConfig
from .live_datafeed import LiveDataFeed
from .live_account_store import LiveAccountStore
from .live_cluster import MatrixLiveCluster

from tezaver.matrix.core.guardrail import (
    GuardrailController,
    GuardrailConfig,
    GuardrailEnvironment,
)
from tezaver.matrix.core.profile import MatrixProfileRepository


def build_silver_15m_live_cluster(
    initial_capital: float = 100.0,
    coin_page_root: Path | None = None,
) -> MatrixLiveCluster:
    """
    BTC/ETH/SOL Silver 15m profillerinden LIVE cluster oluşturur.
    
    Args:
        initial_capital: Starting capital for each cell.
        coin_page_root: Root path for coin profiles (default: data/coin_profiles).
        
    Returns:
        MatrixLiveCluster ready for tick processing.
    """
    if coin_page_root is None:
        coin_page_root = Path("data/coin_profiles")
    
    repo = MatrixProfileRepository(coin_page_root)

    # CoinPage V2'de tanımlı profile_id'ler:
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    cells: list[LiveStrategyCellConfig] = []

    for sym in symbols:
        base = sym.replace("USDT", "")
        profile_id = f"{base}_SILVER_15M_CORE_V1"
        cells.append(
            LiveStrategyCellConfig(
                symbol=sym,
                timeframe="15m",
                profile_id=profile_id,
                risk_mode="contract",
            )
        )

    live_cfg = MatrixLiveConfig(
        environment=GuardrailEnvironment.LIVE,
        initial_capital=initial_capital,
        cells=cells,
    )

    guardrail = GuardrailController(GuardrailConfig())

    return MatrixLiveCluster(
        live_config=live_cfg,
        profile_repo=repo,
        guardrail=guardrail,
    )


__all__ = [
    "MatrixLiveConfig",
    "LiveStrategyCellConfig",
    "LiveDataFeed",
    "LiveAccountStore",
    "MatrixLiveCluster",
    "build_silver_15m_live_cluster",
]
