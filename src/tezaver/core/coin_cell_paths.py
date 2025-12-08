from pathlib import Path

def get_project_root() -> Path:
    """
    Returns the project root directory.
    Assumes this file is at src/tezaver/core/coin_cell_paths.py
    Project root is ../../../ relative to this file.
    """
    current_file = Path(__file__).resolve()
    # src/tezaver/core/coin_cell_paths.py -> core -> tezaver -> src -> root
    project_root = current_file.parent.parent.parent.parent
    return project_root

def get_coin_cells_root() -> Path:
    """
    Returns the path to the 'coin_cells' directory in the project root.
    Creates it if it doesn't exist.
    """
    root = get_project_root()
    coin_cells_dir = root / "coin_cells"
    if not coin_cells_dir.exists():
        coin_cells_dir.mkdir(parents=True, exist_ok=True)
    return coin_cells_dir

def get_coin_cell_dir(symbol: str) -> Path:
    """
    Returns the path to a specific coin's cell directory.
    e.g., coin_cells/BTCUSDT
    Creates it if it doesn't exist.
    """
    root = get_coin_cells_root()
    cell_dir = root / symbol
    if not cell_dir.exists():
        cell_dir.mkdir(parents=True, exist_ok=True)
    return cell_dir

def get_coin_data_dir(symbol: str) -> Path:
    """
    Returns the path to the 'data' directory within a coin's cell.
    e.g., coin_cells/BTCUSDT/data
    Creates it if it doesn't exist.
    """
    cell_dir = get_coin_cell_dir(symbol)
    data_dir = cell_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_history_file(symbol: str, timeframe: str) -> Path:
    """
    Returns the path to the history parquet file for a given symbol and timeframe.
    e.g., coin_cells/BTCUSDT/data/history_15m.parquet
    Does NOT create the file, only returns the path.
    """
    data_dir = get_coin_data_dir(symbol)
    filename = f"history_{timeframe}.parquet"
    return data_dir / filename

def get_library_root() -> Path:
    """
    Returns the library/ directory in project root.
    Creates it if it doesn't exist.
    """
    root = get_project_root()
    library_dir = root / "library"
    if not library_dir.exists():
        library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir

def get_fast15_rallies_dir(symbol: str) -> Path:
    """
    Returns library/fast15_rallies/{SYMBOL}/ directory.
    Creates it if it doesn't exist.
    """
    lib_root = get_library_root()
    fast15_dir = lib_root / "fast15_rallies" / symbol
    if not fast15_dir.exists():
        fast15_dir.mkdir(parents=True, exist_ok=True)
    return fast15_dir

def get_fast15_rallies_path(symbol: str) -> Path:
    """
    Returns library/fast15_rallies/{SYMBOL}/fast15_rallies.parquet path.
    Does NOT create the file, only returns the path.
    """
    return get_fast15_rallies_dir(symbol) / "fast15_rallies.parquet"

def get_coin_profile_dir(symbol: str) -> Path:
    """
    Returns the profile directory for a specific symbol.
    data/coin_profiles/{SYMBOL}/
    Creates it if it doesn't exist.
    """
    root = get_project_root()
    profile_dir = root / "data" / "coin_profiles" / symbol
    if not profile_dir.exists():
        profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir

def get_fast15_rallies_summary_path(symbol: str) -> Path:
    """
    Returns data/coin_profiles/{SYMBOL}/fast15_rallies_summary.json path.
    Uses existing coin_profile directory structure.
    Does NOT create the file, only returns the path.
    """
    return get_coin_profile_dir(symbol) / "fast15_rallies_summary.json"


def get_time_labs_rallies_dir(symbol: str, timeframe: str) -> Path:
    """
    Returns library/time_labs/{TF}/{SYMBOL}/ directory.
    Creates it if it doesn't exist.
    """
    lib_root = get_library_root()
    # library/time_labs/1h/BTCUSDT
    labs_dir = lib_root / "time_labs" / timeframe / symbol
    if not labs_dir.exists():
        labs_dir.mkdir(parents=True, exist_ok=True)
    return labs_dir


def get_time_labs_rallies_path(symbol: str, timeframe: str) -> Path:
    """
    Returns library/time_labs/{TF}/{SYMBOL}/rallies_{TF}.parquet path.
    Does NOT create the file, only returns the path.
    """
    return get_time_labs_rallies_dir(symbol, timeframe) / f"rallies_{timeframe}.parquet"


def get_time_labs_rallies_summary_path(symbol: str, timeframe: str) -> Path:
    """
    Returns data/coin_profiles/{SYMBOL}/time_labs_{TF}_summary.json path.
    Uses existing coin_profile directory structure.
    Does NOT create the file, only returns the path.
    """
    return get_coin_profile_dir(symbol) / f"time_labs_{timeframe}_summary.json"

def get_sim_promotion_path(symbol: str) -> Path:
    """
    Returns data/coin_profiles/{SYMBOL}/sim_promotion.json path.
    """
    return get_coin_profile_dir(symbol) / "sim_promotion.json"
