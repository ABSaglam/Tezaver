import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from .models import CoinState, DataState

DATA_FILE_NAME = "coin_state.json"
DEFAULT_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "POLUSDT",
    "LINKUSDT", "ATOMUSDT", "LTCUSDT", "UNIUSDT", "NEARUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT"
]

def get_data_dir() -> Path:
    """
    Returns the path to the data directory, creating it if it doesn't exist.
    Assumes the project root is 2 levels up from this file's parent (src/tezaver/core -> src/tezaver -> src -> root).
    Actually, let's be safer and look for 'data' relative to the current working directory or a known structure.
    For this skeleton, we'll assume the script is run from project root or we find 'data' in project root.
    """
    # Assuming we run from project root, or we can find it relative to this file
    # This file is in src/tezaver/core/state_store.py
    # Project root is ../../../
    
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    data_dir = project_root / "data"
    
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        
    return data_dir

def _serialize_coin_state(state: CoinState) -> dict:
    """Helper to serialize CoinState to dict."""
    data = state.__dict__.copy()
    data['data_state'] = state.data_state.value
    if state.last_update:
        data['last_update'] = state.last_update.isoformat()
    return data

def _deserialize_coin_state(data: dict) -> CoinState:
    """Helper to deserialize dict to CoinState."""
    # Handle Enum
    if 'data_state' in data:
        try:
            data['data_state'] = DataState(data['data_state'])
        except ValueError:
            data['data_state'] = DataState.MISSING
            
    # Handle datetime
    if 'last_update' in data and data['last_update']:
        try:
            data['last_update'] = datetime.fromisoformat(data['last_update'])
        except ValueError:
            data['last_update'] = None
            
    return CoinState(**data)

def load_coin_states() -> List[CoinState]:
    """
    Loads CoinStates from the JSON file.
    If file doesn't exist, creates a default list and saves it.
    """
    data_dir = get_data_dir()
    file_path = data_dir / DATA_FILE_NAME
    
    if not file_path.exists():
        # Create default states
        default_states = []
        for symbol in DEFAULT_COINS:
            default_states.append(CoinState(symbol=symbol))
        save_coin_states(default_states)
        return default_states
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data_list = json.load(f)
            return [_deserialize_coin_state(item) for item in data_list]
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading coin states: {e}. Returning defaults.")
        # Fallback to defaults if file is corrupt
        default_states = []
        for symbol in DEFAULT_COINS:
            default_states.append(CoinState(symbol=symbol))
        return default_states

def save_coin_states(states: List[CoinState]) -> None:
    """
    Saves the list of CoinStates to the JSON file.
    """
    data_dir = get_data_dir()
    file_path = data_dir / DATA_FILE_NAME
    
    serialized_data = [_serialize_coin_state(state) for state in states]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(serialized_data, f, indent=2, ensure_ascii=False)

def find_coin_state(states: List[CoinState], symbol: str) -> Optional[CoinState]:
    """
    Finds a CoinState by symbol.
    """
    for state in states:
        if state.symbol == symbol:
            return state
    return None
