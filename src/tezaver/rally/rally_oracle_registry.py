"""
Rally Oracle Registry
=====================

Rally Oracle v1 (REV.02) - Dataset Freeze Approach

Instead of expecting the scanner to reproduce exact counts, Rally Oracle v1
is now defined as a **frozen dataset** - a preserved set of rally events
that serves as a golden baseline for comparison and research.

This module provides:
- Registry of available Oracle datasets (symbol + timeframe pairs)
- Loader function to access Oracle datasets
- Read-only access (Oracle datasets are NEVER modified)

Current Oracle Datasets:
- SOLUSDT 15m: 77 rallies (GOLDEN_77 baseline)
"""

from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

from tezaver.core.config import GOLDEN_FAST15_SOL_77_PATH
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


# Oracle Dataset Registry
# (symbol, timeframe) -> Path to frozen parquet file
_ORACLE_DATASETS: Dict[Tuple[str, str], Path] = {
    ("SOLUSDT", "15m"): Path(GOLDEN_FAST15_SOL_77_PATH),
    # Future: Add more Oracle datasets here as needed
    # ("BTCUSDT", "15m"): Path("..."),
}


def has_rally_oracle_dataset(symbol: str, timeframe: str) -> bool:
    """
    Check if an Oracle dataset exists for the given symbol and timeframe.
    
    Args:
        symbol: Coin symbol (e.g., "SOLUSDT")
        timeframe: Timeframe (e.g., "15m")
    
    Returns:
        True if Oracle dataset registered, False otherwise
    """
    key = (symbol.upper(), timeframe)
    return key in _ORACLE_DATASETS


def load_rally_oracle_events(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load Rally Oracle v1 dataset for the given symbol and timeframe.
    
    Rally Oracle datasets are **frozen** - they represent a preserved
    set of rally events from a specific scan at a specific point in time.
    These datasets are READ-ONLY and serve as golden baselines.
    
    Current available datasets:
    - SOLUSDT 15m: 77 rallies (GOLDEN_77 baseline)
    
    Args:
        symbol: Coin symbol (e.g., "SOLUSDT")
        timeframe: Timeframe (e.g., "15m")
    
    Returns:
        DataFrame with Oracle rally events
    
    Raises:
        ValueError: If no Oracle dataset registered for this pair
        FileNotFoundError: If Oracle dataset file not found
    
    Example:
        >>> df = load_rally_oracle_events("SOLUSDT", "15m")
        >>> len(df)
        77
    """
    key = (symbol.upper(), timeframe)
    
    if key not in _ORACLE_DATASETS:
        available = ", ".join([f"{s}/{tf}" for s, tf in _ORACLE_DATASETS.keys()])
        raise ValueError(
            f"No Oracle dataset registered for {symbol}/{timeframe}. "
            f"Available: {available}"
        )
    
    path = _ORACLE_DATASETS[key]
    
    if not path.exists():
        raise FileNotFoundError(
            f"Oracle dataset not found at {path}. "
            f"Expected location for {symbol}/{timeframe} Oracle data."
        )
    
    logger.info(f"Loading Rally Oracle v1 dataset: {symbol}/{timeframe} from {path}")
    
    df = pd.read_parquet(path)
    
    logger.info(f"Oracle dataset loaded: {len(df)} rallies")
    
    return df


def get_oracle_dataset_info(symbol: str, timeframe: str) -> Dict:
    """
    Get metadata about an Oracle dataset without loading it.
    
    Args:
        symbol: Coin symbol
        timeframe: Timeframe
    
    Returns:
        Dict with 'path', 'exists', 'size_bytes' (if exists)
    
    Raises:
        ValueError: If no Oracle dataset registered
    """
    key = (symbol.upper(), timeframe)
    
    if key not in _ORACLE_DATASETS:
        raise ValueError(f"No Oracle dataset registered for {symbol}/{timeframe}")
    
    path = _ORACLE_DATASETS[key]
    
    info = {
        'symbol': symbol.upper(),
        'timeframe': timeframe,
        'path': str(path),
        'exists': path.exists()
    }
    
    if path.exists():
        info['size_bytes'] = path.stat().st_size
    
    return info


def list_available_oracle_datasets() -> list:
    """
    List all registered Oracle datasets.
    
    Returns:
        List of (symbol, timeframe) tuples
    """
    return list(_ORACLE_DATASETS.keys())
