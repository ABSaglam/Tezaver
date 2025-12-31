"""
Coin Class Utilities
====================
Defines coin character classes for Simyacı DNA mining.

Classes:
    A - Aristocrats: BTC, ETH, SOL - High volume, clean candles
    B - Standard: DOT, LINK, UNI - Solid mid-cap altcoins
    C - Aggressive: Meme coins, low-cap wick monsters
    D - Zombies: Dead, no-volume coins (Blacklist)
    N - Newbies: Newly listed coins (<30 days)
"""
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from enum import Enum

# ============================================================
# COIN CLASS DEFINITIONS
# ============================================================

class CoinClass(str, Enum):
    """Coin character classification."""
    A = "A"  # Aristocrats
    B = "B"  # Standard
    C = "C"  # Aggressive
    D = "D"  # Zombies
    N = "N"  # Newbies

# Class metadata for UI display
COIN_CLASS_INFO: Dict[str, Dict[str, Any]] = {
    "A": {
        "name": "Aristokrat",
        "name_en": "Aristocrat",
        "icon": "👑",
        "color": "#FFD700",  # Gold
        "description": "Majör coinler: BTC, ETH, SOL. Yüksek hacim, temiz mumlar.",
        "strategy": "Dar stop-loss, hassas giriş",
        "position_modifier": 1.0,  # Full position
        "stop_loss_modifier": 1.0,  # Standard SL
    },
    "B": {
        "name": "Standart",
        "name_en": "Standard",
        "icon": "🔷",
        "color": "#4169E1",  # Royal Blue
        "description": "Sağlam altcoinler: DOT, LINK, UNI, AVAX.",
        "strategy": "Standart parametreler",
        "position_modifier": 1.0,
        "stop_loss_modifier": 1.0,
    },
    "C": {
        "name": "Agresif",
        "name_en": "Aggressive",
        "icon": "⚡",
        "color": "#FF4500",  # Orange Red
        "description": "Meme coinler, düşük hacim, iğneciler.",
        "strategy": "Geniş stop-loss, breakout onayı bekle",
        "position_modifier": 0.5,  # Half position
        "stop_loss_modifier": 1.5,  # 50% wider SL
    },
    "D": {
        "name": "Zombi",
        "name_en": "Zombie",
        "icon": "💀",
        "color": "#808080",  # Gray
        "description": "Hacimsiz, ölü projeler. İşlem yapılmaz.",
        "strategy": "KARA LİSTE - Taramaya dahil edilmez",
        "position_modifier": 0.0,
        "stop_loss_modifier": 0.0,
    },
    "N": {
        "name": "Yeni",
        "name_en": "Newbie",
        "icon": "🆕",
        "color": "#32CD32",  # Lime Green
        "description": "Yeni listelenen coinler (<30 gün).",
        "strategy": "VUR-KAÇ modu: Küçük pozisyon, hızlı çıkış",
        "position_modifier": 0.25,  # Quarter position
        "stop_loss_modifier": 1.3,
    },
}

# ============================================================
# PREDEFINED COIN CLASS ASSIGNMENTS
# ============================================================

# Class A - Aristocrats (Major coins)
CLASS_A_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
]

# Class B - Standard (Solid altcoins)
CLASS_B_COINS = [
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT",
    "LTCUSDT", "UNIUSDT", "ATOMUSDT", "APTUSDT", "NEARUSDT",
    "OPUSDT", "ARBUSDT", "INJUSDT", "SUIUSDT", "SEIUSDT",
    "FILUSDT", "AAVEUSDT", "MKRUSDT", "SNXUSDT", "COMPUSDT",
]

# Class C - Aggressive (Meme & volatile)
CLASS_C_COINS = [
    "DOGEUSDT", "SHIBUSDT", "PEPEUSDT", "FLOKIUSDT", "BONKUSDT",
    "WIFUSDT", "MEMEUSDT", "BOMEUSDT",
]

# Class D - Zombies (Dead coins - blacklist)
CLASS_D_COINS = [
    # Add coins with no volume / dead projects
]

# ============================================================
# COIN CLASS DETECTION
# ============================================================

def get_coin_class(symbol: str, listing_date: Optional[datetime] = None) -> str:
    """
    Determine the class of a coin.
    
    Args:
        symbol: Coin symbol (e.g., "BTCUSDT")
        listing_date: Optional listing date for newbie detection
        
    Returns:
        Class code: "A", "B", "C", "D", or "N"
    """
    symbol_upper = symbol.upper()
    
    # Check if newbie (listed < 30 days ago)
    if listing_date:
        days_since_listing = (datetime.now() - listing_date).days
        if days_since_listing < 30:
            return "N"
    
    # Check predefined lists
    if symbol_upper in CLASS_A_COINS:
        return "A"
    if symbol_upper in CLASS_B_COINS:
        return "B"
    if symbol_upper in CLASS_C_COINS:
        return "C"
    if symbol_upper in CLASS_D_COINS:
        return "D"
    
    # Default to Standard for unknown coins
    return "B"


def get_coin_class_display(coin_class: str) -> str:
    """
    Get display string for coin class.
    
    Args:
        coin_class: Class code ("A", "B", "C", "D", "N")
        
    Returns:
        Display string like "👑 Aristokrat (A)"
    """
    info = COIN_CLASS_INFO.get(coin_class, COIN_CLASS_INFO["B"])
    return f"{info['icon']} {info['name']} ({coin_class})"


def get_coin_class_icon(coin_class: str) -> str:
    """Get icon for coin class."""
    return COIN_CLASS_INFO.get(coin_class, {}).get("icon", "❓")


def get_coin_class_color(coin_class: str) -> str:
    """Get color for coin class."""
    return COIN_CLASS_INFO.get(coin_class, {}).get("color", "#808080")


def is_tradeable_class(coin_class: str) -> bool:
    """Check if coin class is tradeable (not zombie)."""
    return coin_class != "D"


def get_position_modifier(coin_class: str) -> float:
    """Get position size modifier for coin class."""
    return COIN_CLASS_INFO.get(coin_class, {}).get("position_modifier", 1.0)


def get_stop_loss_modifier(coin_class: str) -> float:
    """Get stop-loss modifier for coin class."""
    return COIN_CLASS_INFO.get(coin_class, {}).get("stop_loss_modifier", 1.0)


# ============================================================
# CLASS OVERRIDE MANAGEMENT
# ============================================================

# Store for manual class overrides (symbol -> class)
_class_overrides: Dict[str, str] = {}

def set_coin_class_override(symbol: str, new_class: str) -> None:
    """
    Manually override the class of a coin.
    
    Args:
        symbol: Coin symbol
        new_class: New class code ("A", "B", "C", "D", "N")
    """
    if new_class in COIN_CLASS_INFO:
        _class_overrides[symbol.upper()] = new_class


def get_coin_class_with_override(symbol: str, listing_date: Optional[datetime] = None) -> str:
    """
    Get coin class, considering manual overrides.
    
    Args:
        symbol: Coin symbol
        listing_date: Optional listing date
        
    Returns:
        Class code, prioritizing override if exists
    """
    symbol_upper = symbol.upper()
    
    # Check override first
    if symbol_upper in _class_overrides:
        return _class_overrides[symbol_upper]
    
    # Fall back to auto-detection
    return get_coin_class(symbol_upper, listing_date)


def clear_class_override(symbol: str) -> None:
    """Remove manual class override for a coin."""
    symbol_upper = symbol.upper()
    if symbol_upper in _class_overrides:
        del _class_overrides[symbol_upper]
