# Matrix V2 Profile Module
"""
Profile management for Matrix cells.

Supports both v1 (LEGACY) and v2 (CURRENT) coin page formats.
V2 is tried first; falls back to v1 if not found.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tezaver.matrix.coin_page.loader import (
    load_coin_strategy_page,
    load_coin_strategy_page_v2,
)
from tezaver.matrix.coin_page.schema import (
    StrategyConfigV1,
    StrategyBenchmarkV1,
    StrategyRiskContractV1,
    StrategyRuntimeMode,
)


@dataclass
class MatrixCellProfile:
    """
    Represents a single cell in the Matrix trading grid.
    
    Each cell is a unique combination of symbol, timeframe, and grade.
    
    V2 fields (strategy_config, benchmark, risk_contract, runtime_mode)
    are populated when loading from CoinStrategyPageV2.
    """
    profile_id: str
    symbol: str
    timeframe: str
    grade: str  # e.g., "diamond", "gold", "silver", "bronze"
    status: str  # "APPROVED" | "EXPERIMENTAL" | "DISABLED"
    strategy_card_path: str
    matrix_role: str  # "default" | "experimental" | "disabled"
    metadata: dict[str, object] = field(default_factory=dict)
    # V2 fields (optional, populated from CoinStrategyPageV2)
    kind: Optional[str] = None  # e.g., "silver_15m_core"
    strategy_config: Optional[StrategyConfigV1] = None
    benchmark: Optional[StrategyBenchmarkV1] = None
    risk_contract: Optional[StrategyRiskContractV1] = None
    runtime_mode: Optional[StrategyRuntimeMode] = None


class MatrixProfileRepository:
    """
    Repository that reads coin-level CoinStrategyPage JSON files
    and exposes MatrixCellProfile objects to the rest of Matrix.
    
    V2-first loading: tries matrix_coin_page_v2.json first,
    falls back to matrix_coin_page_v1.json if not found.
    """
    
    def __init__(self, coin_page_root: Path) -> None:
        """
        Initialize repository with root path for coin pages.
        
        Args:
            coin_page_root: Root directory containing coin strategy pages.
                           e.g., data/coin_profiles/
        """
        self._root = coin_page_root
        self._cache: dict[str, list[MatrixCellProfile]] = {}
    
    def _get_coin_page_path_v2(self, symbol: str) -> Path:
        """Get path to v2 coin page: matrix_coin_page_v2.json."""
        return self._root / symbol / "matrix_coin_page_v2.json"
    
    def _get_coin_page_path_v1(self, symbol: str) -> Path:
        """Get path to v1 coin page: matrix_coin_page_v1.json (LEGACY)."""
        return self._root / symbol / "matrix_coin_page_v1.json"
    
    # Alias for backward compatibility
    def _get_coin_page_path(self, symbol: str) -> Path:
        """LEGACY: Get the path to a coin's strategy page JSON."""
        return self._get_coin_page_path_v1(symbol)
    
    def load_profiles_for_symbol(self, symbol: str) -> list[MatrixCellProfile]:
        """
        Load all profiles for a given symbol.
        
        Tries v2 first, falls back to v1 if not found.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            
        Returns:
            List of MatrixCellProfile for the symbol.
        """
        if symbol in self._cache:
            return self._cache[symbol]
        
        # Try v2 first
        v2_path = self._get_coin_page_path_v2(symbol)
        if v2_path.exists():
            profiles = self._load_from_v2(symbol, v2_path)
            self._cache[symbol] = profiles
            return profiles
        
        # Fall back to v1
        v1_path = self._get_coin_page_path_v1(symbol)
        profiles = self._load_from_v1(symbol, v1_path)
        self._cache[symbol] = profiles
        return profiles
    
    def _load_from_v2(self, symbol: str, path: Path) -> list[MatrixCellProfile]:
        """Load profiles from CoinStrategyPageV2."""
        page = load_coin_strategy_page_v2(path)
        
        profiles: list[MatrixCellProfile] = []
        for tf_key, tf_strategies in page.timeframes.items():
            for profile_id, p in tf_strategies.profiles.items():
                profiles.append(
                    MatrixCellProfile(
                        profile_id=p.profile_id,
                        symbol=page.symbol,
                        timeframe=tf_strategies.tf,
                        grade=self._kind_to_grade(p.kind),
                        status=p.status,
                        strategy_card_path="",  # Not used in v2
                        matrix_role="default" if p.runtime_mode.enabled else "disabled",
                        metadata={},
                        # V2 fields
                        kind=p.kind,
                        strategy_config=p.strategy,
                        benchmark=p.benchmark_v1,
                        risk_contract=p.risk_contract_v1,
                        runtime_mode=p.runtime_mode,
                    )
                )
        
        return profiles
    
    def _load_from_v1(self, symbol: str, path: Path) -> list[MatrixCellProfile]:
        """LEGACY: Load profiles from CoinStrategyPage v1."""
        page = load_coin_strategy_page(path)
        
        profiles: list[MatrixCellProfile] = []
        for timeframe, tf_cfg in page.timeframes.items():
            for p in tf_cfg.profiles:
                profiles.append(
                    MatrixCellProfile(
                        profile_id=p.profile_id,
                        symbol=page.symbol,
                        timeframe=timeframe,
                        grade=p.grade,
                        status=p.status,
                        strategy_card_path=p.strategy_card,
                        matrix_role=p.matrix_role,
                        metadata=p.metadata,
                    )
                )
        
        return profiles
    
    @staticmethod
    def _kind_to_grade(kind: str) -> str:
        """Map kind (e.g., 'silver_15m_core') to grade (e.g., 'silver')."""
        if "diamond" in kind:
            return "diamond"
        elif "gold" in kind:
            return "gold"
        elif "silver" in kind:
            return "silver"
        elif "bronze" in kind:
            return "bronze"
        return "unknown"
    
    def get_profile(self, profile_id: str) -> MatrixCellProfile | None:
        """
        Get a specific profile by ID.
        
        Args:
            profile_id: Unique profile identifier.
            
        Returns:
            MatrixCellProfile if found, None otherwise.
        """
        # Search in cached symbols first
        for symbol in self._cache:
            for p in self._cache[symbol]:
                if p.profile_id == profile_id:
                    return p
        
        # Try to parse profile_id to find symbol
        # Convention: BTC_SILVER_15M_CORE_V1 → symbol could be "BTCUSDT"
        # For now, return None if not in cache
        return None
    
    def load_all_from_coin_page_v2(self, symbol: str) -> list[MatrixCellProfile]:
        """
        Explicitly load profiles from CoinStrategyPageV2.
        
        Raises FileNotFoundError if v2 page doesn't exist.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            
        Returns:
            List of MatrixCellProfile from v2 page.
        """
        v2_path = self._get_coin_page_path_v2(symbol)
        if not v2_path.exists():
            raise FileNotFoundError(
                f"matrix_coin_page_v2.json not found for {symbol}"
            )
        
        profiles = self._load_from_v2(symbol, v2_path)
        self._cache[symbol] = profiles
        return profiles
    
    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()

