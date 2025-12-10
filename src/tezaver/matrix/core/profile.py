# Matrix V2 Profile Module
"""
Profile management for Matrix cells.
"""

from dataclasses import dataclass, field
from pathlib import Path

from tezaver.matrix.coin_page.loader import load_coin_strategy_page


@dataclass
class MatrixCellProfile:
    """
    Represents a single cell in the Matrix trading grid.
    
    Each cell is a unique combination of symbol, timeframe, and grade.
    """
    profile_id: str
    symbol: str
    timeframe: str
    grade: str  # e.g., "diamond", "gold", "silver", "bronze"
    status: str  # "APPROVED" | "EXPERIMENTAL" | "DISABLED"
    strategy_card_path: str
    matrix_role: str  # "default" | "experimental" | "disabled"
    metadata: dict[str, object] = field(default_factory=dict)


class MatrixProfileRepository:
    """
    Repository that reads coin-level CoinStrategyPage JSON files
    and exposes MatrixCellProfile objects to the rest of Matrix.
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
    
    def _get_coin_page_path(self, symbol: str) -> Path:
        """
        Get the path to a coin's strategy page JSON.
        
        Example: data/coin_profiles/BTCUSDT/matrix_coin_page_v1.json
        """
        filename = "matrix_coin_page_v1.json"
        return self._root / symbol / filename
    
    def load_profiles_for_symbol(self, symbol: str) -> list[MatrixCellProfile]:
        """
        Load all profiles for a given symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            
        Returns:
            List of MatrixCellProfile for the symbol.
        """
        if symbol in self._cache:
            return self._cache[symbol]
        
        path = self._get_coin_page_path(symbol)
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
        
        self._cache[symbol] = profiles
        return profiles
    
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
    
    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()
