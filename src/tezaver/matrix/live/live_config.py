# Matrix V2 Live Config
"""
Configuration for live trading.
"""

from dataclasses import dataclass, field
from typing import List, Literal

from tezaver.matrix.core.guardrail import GuardrailEnvironment


@dataclass
class LiveStrategyCellConfig:
    """
    Tek bir Matrix hücresini (symbol + timeframe + profile) temsil eder.
    Örnek: BTCUSDT 15m Silver Core.
    """
    symbol: str
    timeframe: str
    profile_id: str
    risk_mode: Literal["contract", "experiment"] = "contract"
    state_file_path: str | None = None  # JSON state file for persistence


@dataclass
class MatrixLiveConfig:
    """
    Matrix Live cluster genel konfigürasyonu.
    """
    environment: GuardrailEnvironment = GuardrailEnvironment.LIVE
    initial_capital: float = 1000.0
    cells: List[LiveStrategyCellConfig] = field(default_factory=list)
