"""
Tezaver Mac - Central Configuration (M19_CONFIG_CORE)

This module contains all system-wide constants, thresholds, and settings.
It serves as the single source of truth for configuration.
"""

from typing import List, Dict
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Environment Settings ---
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# --- API Credentials (from environment) ---
# IMPORTANT: Never commit actual API keys to Git!
# Set these in your .env file (see .env.example)
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', '')

# --- Timezone Settings ---
# UTC offset for Turkey (UTC+3)
TIMEZONE_OFFSET_HOURS = int(os.getenv('TIMEZONE_OFFSET_HOURS', '3'))

from datetime import datetime, timedelta, timezone

def get_turkey_now() -> datetime:
    """Returns current time in Turkey timezone (UTC+3)."""
    tz = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))
    return datetime.now(tz)

def to_turkey_time(dt: datetime) -> datetime:
    """Converts a datetime object to Turkey timezone."""
    if dt is None:
        return None
    tz = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))
    if dt.tzinfo is None:
        # Assume UTC if naive
        return dt.replace(tzinfo=timezone.utc).astimezone(tz)
    return dt.astimezone(tz)

def format_date_tr(dt: datetime, format_str: str = "%d %B %Y", include_time: bool = False) -> str:
    """
    Formats a datetime object with Turkish month names.
    Supports standard strftime directives.
    
    Args:
        dt: Datetime object (will be converted to TR time first)
        format_str: Format string (e.g. "%d %B %Y")
        include_time: If True, appends time in HH:MM format if not in format_str
    
    Returns:
        Formatted string in Turkish
    """
    dt_tr = to_turkey_time(dt)
    
    # Turkish month names
    months = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
        7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }
    
    # Turkish day names (optional usage)
    days = {
        0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe",
        4: "Cuma", 5: "Cumartesi", 6: "Pazar"
    }
    
    # Replace full month name %B
    formatted = format_str.replace("%B", months[dt_tr.month])
    
    # Replace abbreviated month name %b (using first 3 letters)
    formatted = formatted.replace("%b", months[dt_tr.month][:3])
    
    # Replace full day name %A
    formatted = formatted.replace("%A", days[dt_tr.weekday()])
    
    # Replace abbreviated day name %a
    formatted = formatted.replace("%a", days[dt_tr.weekday()][:3])
    
    # Do standard formatting for the rest
    return dt_tr.strftime(formatted)


# --- UI Configuration ---
# Logo dimensions (pixels)
UI_LOGO_WIDTH_PX = int(os.getenv('UI_LOGO_WIDTH_PX', '400'))
UI_LOGO_HEIGHT_PX = int(os.getenv('UI_LOGO_HEIGHT_PX', '80'))


# --- Coin & Timeframe Settings ---
DEFAULT_COINS: List[str] = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "POLUSDT",
    "LINKUSDT",
    "ATOMUSDT",
    "LTCUSDT",
    "UNIUSDT",
    "NEARUSDT",
    "APTUSDT",
    "ARBUSDT",
    "OPUSDT",
    "INJUSDT",
    "SUIUSDT",
]

DEFAULT_HISTORY_TIMEFRAMES: List[str] = ["15m", "1h", "4h", "1d", "1w"]
DEFAULT_FEATURE_TIMEFRAMES: List[str] = DEFAULT_HISTORY_TIMEFRAMES
DEFAULT_SNAPSHOT_BASE_TFS: List[str] = ["1h", "4h", "1d", "1w"]

# Mapping for Multi-TF Snapshots
# Defines which timeframes are included when building a multi-tf snapshot for a base timeframe
MULTI_TF_MAPPING: Dict[str, List[str]] = {
    "1h": ["15m", "1h", "4h", "1d"],
    "4h": ["1h", "4h", "1d", "1w"],
    "1d": ["4h", "1d", "1w"],
    "1w": ["1d", "1w"],
}

# Turkish timeframe labels
TIMEFRAME_LABELS: Dict[str, str] = {
    "15m": "15dk",
    "1h": "1sa",
    "4h": "4sa", 
    "1d": "1gn",
    "1w": "1hf",
}

def get_tf_label(tf: str) -> str:
    """Get Turkish label for a timeframe."""
    return TIMEFRAME_LABELS.get(tf, tf)

# --- Rally Labeling Settings ---
# Thresholds for defining a rally (e.g. 0.05 means 5% gain)
RALLY_THRESHOLDS: List[float] = [0.05, 0.10, 0.20]

# How many bars to look ahead to determine the outcome
LOOKAHEAD_BARS_MAP: Dict[str, int] = {
    "15m": 96,  # 24 hours
    "1h": 48,   # 2 days
    "4h": 36,   # 6 days
    "1d": 14,   # 2 weeks
    "1w": 8,    # 2 months
}
DEFAULT_LOOKAHEAD_BARS: int = 50

# --- Pattern Wisdom Settings ---
MIN_PATTERN_SAMPLES: int = 20
TRUST_THRESHOLD: float = 0.5
BETRAYAL_THRESHOLD: float = 0.3

# --- Backup Settings ---
BACKUP_DIR_NAME: str = "backups"
BACKUP_MAX_FILES: int = 20

# --- Level Settings ---
DEFAULT_LEVEL_TIMEFRAMES: List[str] = ["1h", "4h", "1d", "1w"]

# --- M23 Chart Settings ---
# Window size for chart display around an event
CHART_WINDOW_BEFORE: int = 60  # bars before event
CHART_WINDOW_AFTER: int = 40   # bars after event
DEFAULT_CHART_TIMEFRAME: str = "1h"  # fallback timeframe if not specified

# --- Fast15 Rally Scanner Settings ---
FAST15_RALLY_TF: str = "15m"
FAST15_LOOKAHEAD_BARS: int = 21  # 1-21 bars lookahead window
FAST15_RALLY_BUCKETS: List[float] = [0.05, 0.10, 0.20, 0.30]  # 5%, 10%, 20%, 30%
FAST15_MIN_GAIN: float = 0.05  # Minimum 5% gain to qualify as rally
FAST15_EVENT_GAP: int = 3  # Minimum 3 bars between events to prevent overlap

# MACD Phase classification thresholds for Fast15
FAST15_MACD_SLEEP_THRESHOLD: float = 0.0005  # Very small histogram = sleep
FAST15_MACD_WAKE_THRESHOLD: float = 0.001    # Rising from sleep = awakening
FAST15_MACD_RUN_THRESHOLD: float = 0.003     # Strong positive momentum = running


# --- Time-Labs v1 Settings ---
TIME_LABS_TFS: List[str] = ["1h", "4h"]

TIME_LABS_LOOKAHEAD_BARS: Dict[str, int] = {
    "1h": 10,  # 1-10 bars window (~10 hours)
    "4h": 10,  # 1-10 bars window (~40 hours)
}

TIME_LABS_RALLY_BUCKETS: List[float] = [0.05, 0.10, 0.20, 0.30]  # 5%, 10%, 20%, 30%

TIME_LABS_MIN_GAIN: Dict[str, float] = {
    "1h": 0.05,  # 5%
    "4h": 0.07,  # 7%
}

TIME_LABS_EVENT_GAP: Dict[str, int] = {
    "1h": 3,
    "4h": 2,
}

# --- Indicator Settings ---
# Global defaults for technical indicators
RSI_PERIOD: int = 11
RSI_EMA_PERIOD: int = 11

MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9

ATR_PERIOD: int = 14
