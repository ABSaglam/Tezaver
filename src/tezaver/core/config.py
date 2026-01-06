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
# All Binance Futures USDT Perpetual pairs (538 coins)
DEFAULT_COINS: List[str] = [
    "0GUSDT", "1000000BOBUSDT", "1000000MOGUSDT", "1000BONKUSDT", "1000CATUSDT",
    "1000CHEEMSUSDT", "1000FLOKIUSDT", "1000LUNCUSDT", "1000PEPEUSDT", "1000RATSUSDT",
    "1000SATSUSDT", "1000SHIBUSDT", "1000WHYUSDT", "1000XECUSDT", "1INCHUSDT",
    "1MBABYDOGEUSDT", "2ZUSDT", "42USDT", "4USDT", "A2ZUSDT",
    "AAVEUSDT", "ACEUSDT", "ACHUSDT", "ACTUSDT", "ACXUSDT",
    "ADAUSDT", "AERGOUSDT", "AEROUSDT", "AEVOUSDT", "AGLDUSDT",
    "AGTUSDT", "AINUSDT", "AIOTUSDT", "AIOUSDT", "AIUSDT",
    "AIXBTUSDT", "AKEUSDT", "AKTUSDT", "ALCHUSDT", "ALGOUSDT",
    "ALICEUSDT", "ALLOUSDT", "ALLUSDT", "ALPINEUSDT", "ALTUSDT",
    "ANIMEUSDT", "ANKRUSDT", "APEUSDT", "API3USDT", "APRUSDT",
    "APTUSDT", "ARBUSDT", "ARCUSDT", "ARIAUSDT", "ARKMUSDT",
    "ARKUSDT", "ARPAUSDT", "ARUSDT", "ASRUSDT", "ASTERUSDT",
    "ASTRUSDT", "ATAUSDT", "ATHUSDT", "ATOMUSDT", "ATUSDT",
    "AUCTIONUSDT", "AUSDT", "AVAAIUSDT", "AVAUSDT", "AVAXUSDT",
    "AVNTUSDT", "AWEUSDT", "AXLUSDT", "AXSUSDT", "B2USDT",
    "B3USDT", "BABYUSDT", "BANANAS31USDT", "BANANAUSDT", "BANDUSDT",
    "BANKUSDT", "BANUSDT", "BARDUSDT", "BASUSDT", "BATUSDT",
    "BBUSDT", "BCHUSDT", "BDXNUSDT", "BEAMXUSDT", "BEATUSDT",
    "BELUSDT", "BERAUSDT", "BICOUSDT", "BIDUSDT", "BIGTIMEUSDT",
    "BIOUSDT", "BLESSUSDT", "BLUAIUSDT", "BLURUSDT", "BMTUSDT",
    "BNBUSDT", "BNTUSDT", "BOBUSDT", "BOMEUSDT", "BRETTUSDT",
    "BREVUSDT", "BROCCOLI714USDT", "BROCCOLIF3BUSDT", "BRUSDT", "BSVUSDT",
    "BTCDOMUSDT", "BTCUSDT", "BTRUSDT", "BULLAUSDT", "BUSDT",
    "C98USDT", "CAKEUSDT", "CARVUSDT", "CATIUSDT", "CCUSDT",
    "CELOUSDT", "CELRUSDT", "CETUSUSDT", "CFXUSDT", "CGPTUSDT",
    "CHESSUSDT", "CHILLGUYUSDT", "CHRUSDT", "CHZUSDT", "CKBUSDT",
    "CLANKERUSDT", "CLOUSDT", "COAIUSDT", "COLLECTUSDT", "COMMONUSDT",
    "COMPUSDT", "COOKIEUSDT", "COSUSDT", "COTIUSDT", "COWUSDT",
    "CROSSUSDT", "CRVUSDT", "CTKUSDT", "CTSIUSDT", "CUDISUSDT",
    "CUSDT", "CVCUSDT", "CVXUSDT", "CYBERUSDT", "CYSUSDT",
    "DAMUSDT", "DASHUSDT", "DEEPUSDT", "DEGENUSDT", "DEGOUSDT",
    "DENTUSDT", "DEXEUSDT", "DFUSDT", "DIAUSDT", "DMCUSDT",
    "DODOXUSDT", "DOGEUSDT", "DOGSUSDT", "DOLOUSDT", "DOODUSDT",
    "DOTUSDT", "DRIFTUSDT", "DUSDT", "DUSKUSDT", "DYDXUSDT",
    "DYMUSDT", "EDENUSDT", "EDUUSDT", "EGLDUSDT", "EIGENUSDT",
    "ENAUSDT", "ENJUSDT", "ENSOUSDT", "ENSUSDT", "EPICUSDT",
    "EPTUSDT", "ERAUSDT", "ESPORTSUSDT", "ETCUSDT", "ETHFIUSDT",
    "ETHUSDT", "ETHWUSDT", "EULUSDT", "EVAAUSDT", "FARTCOINUSDT",
    "FETUSDT", "FFUSDT", "FHEUSDT", "FIDAUSDT", "FILUSDT",
    "FIOUSDT", "FLOCKUSDT", "FLOWUSDT", "FLUIDUSDT", "FLUXUSDT",
    "FOLKSUSDT", "FORMUSDT", "FORTHUSDT", "FUNUSDT", "FUSDT",
    "FXSUSDT", "GALAUSDT", "GASUSDT", "GHSTUSDT", "GIGGLEUSDT",
    "GLMUSDT", "GMTUSDT", "GMXUSDT", "GOATUSDT", "GPSUSDT",
    "GRASSUSDT", "GRIFFAINUSDT", "GRTUSDT", "GTCUSDT", "GUAUSDT",
    "GUNUSDT", "GUSDT", "HAEDALUSDT", "HANAUSDT", "HBARUSDT",
    "HEIUSDT", "HEMIUSDT", "HFTUSDT", "HIGHUSDT", "HIPPOUSDT",
    "HIVEUSDT", "HMSTRUSDT", "HOLOUSDT", "HOMEUSDT", "HOOKUSDT",
    "HOTUSDT", "HUMAUSDT", "HUSDT", "HYPERUSDT", "HYPEUSDT",
    "ICNTUSDT", "ICPUSDT", "ICXUSDT", "IDOLUSDT", "IDUSDT",
    "ILVUSDT", "IMXUSDT", "INITUSDT", "INJUSDT", "INUSDT",
    "IOSTUSDT", "IOTAUSDT", "IOTXUSDT", "IOUSDT", "IPUSDT",
    "IRUSDT", "IRYSUSDT", "JASMYUSDT", "JCTUSDT", "JELLYJELLYUSDT",
    "JOEUSDT", "JSTUSDT", "JTOUSDT", "JUPUSDT", "KAIAUSDT",
    "KAITOUSDT", "KASUSDT", "KAVAUSDT", "KERNELUSDT", "KGENUSDT",
    "KITEUSDT", "KMNOUSDT", "KNCUSDT", "KOMAUSDT", "KSMUSDT",
    "LABUSDT", "LAUSDT", "LAYERUSDT", "LDOUSDT", "LIGHTUSDT",
    "LINEAUSDT", "LINKUSDT", "LISTAUSDT", "LITUSDT", "LPTUSDT",
    "LQTYUSDT", "LRCUSDT", "LSKUSDT", "LTCUSDT", "LUMIAUSDT",
    "LUNA2USDT", "LYNUSDT", "MAGICUSDT", "MAGMAUSDT", "MANAUSDT",
    "MANTAUSDT", "MASKUSDT", "MAVIAUSDT", "MAVUSDT", "MBOXUSDT",
    "MELANIAUSDT", "MEMEUSDT", "MERLUSDT", "METISUSDT", "METUSDT",
    "MEUSDT", "MEWUSDT", "MINAUSDT", "MIRAUSDT", "MITOUSDT",
    "MLNUSDT", "MMTUSDT", "MOCAUSDT", "MONUSDT", "MOODENGUSDT",
    "MORPHOUSDT", "MOVEUSDT", "MOVRUSDT", "MTLUSDT", "MUBARAKUSDT",
    "MUSDT", "MYXUSDT", "NAORISUSDT", "NEARUSDT", "NEIROUSDT",
    "NEOUSDT", "NEWTUSDT", "NFPUSDT", "NIGHTUSDT", "NILUSDT",
    "NKNUSDT", "NMRUSDT", "NOMUSDT", "NOTUSDT", "NTRNUSDT",
    "NXPCUSDT", "OGNUSDT", "OGUSDT", "OLUSDT", "OMUSDT",
    "ONDOUSDT", "ONEUSDT", "ONGUSDT", "ONTUSDT", "ONUSDT",
    "OPENUSDT", "OPUSDT", "ORCAUSDT", "ORDERUSDT", "ORDIUSDT",
    "OXTUSDT", "PARTIUSDT", "PAXGUSDT", "PENDLEUSDT", "PENGUUSDT",
    "PEOPLEUSDT", "PHAUSDT", "PHBUSDT", "PIEVERSEUSDT", "PIPPINUSDT",
    "PIXELUSDT", "PLAYUSDT", "PLUMEUSDT", "PNUTUSDT", "POLUSDT",
    "POLYXUSDT", "POPCATUSDT", "PORTALUSDT", "POWERUSDT", "POWRUSDT",
    "PROMPTUSDT", "PROMUSDT", "PROVEUSDT", "PTBUSDT", "PUFFERUSDT",
    "PUMPBTCUSDT", "PUMPUSDT", "PUNDIXUSDT", "PYTHUSDT", "QNTUSDT",
    "QTUMUSDT", "QUSDT", "RAREUSDT", "RAVEUSDT", "RAYSOLUSDT",
    "RDNTUSDT", "RECALLUSDT", "REDUSDT", "RENDERUSDT", "RESOLVUSDT",
    "REZUSDT", "RIFUSDT", "RIVERUSDT", "RLCUSDT", "RLSUSDT",
    "RONINUSDT", "ROSEUSDT", "RPLUSDT", "RSRUSDT", "RUNEUSDT",
    "RVNUSDT", "RVVUSDT", "SAFEUSDT", "SAGAUSDT", "SAHARAUSDT",
    "SANDUSDT", "SANTOSUSDT", "SAPIENUSDT", "SCRTUSDT", "SCRUSDT",
    "SEIUSDT", "SENTUSDT", "SFPUSDT", "SHELLUSDT", "SIGNUSDT",
    "SIRENUSDT", "SKLUSDT", "SKYAIUSDT", "SKYUSDT", "SLPUSDT",
    "SNXUSDT", "SOLUSDT", "SOLVUSDT", "SOMIUSDT", "SONICUSDT",
    "SOONUSDT", "SOPHUSDT", "SPELLUSDT", "SPKUSDT", "SPXUSDT",
    "SQDUSDT", "SSVUSDT", "STABLEUSDT", "STBLUSDT", "STEEMUSDT",
    "STGUSDT", "STORJUSDT", "STOUSDT", "STRKUSDT", "STXUSDT",
    "SUIUSDT", "SUNUSDT", "SUPERUSDT", "SUSDT", "SUSHIUSDT",
    "SWARMSUSDT", "SXTUSDT", "SYNUSDT", "SYRUPUSDT", "SYSUSDT",
    "TACUSDT", "TAGUSDT", "TAIKOUSDT", "TAKEUSDT", "TANSSIUSDT",
    "TAOUSDT", "TAUSDT", "THETAUSDT", "THEUSDT", "TIAUSDT",
    "TLMUSDT", "TNSRUSDT", "TONUSDT", "TOSHIUSDT", "TOWNSUSDT",
    "TRADOORUSDT", "TRBUSDT", "TREEUSDT", "TRUMPUSDT", "TRUSTUSDT",
    "TRUTHUSDT", "TRUUSDT", "TRXUSDT", "TSTUSDT", "TURBOUSDT",
    "TURTLEUSDT", "TUSDT", "TUTUSDT", "TWTUSDT", "UAIUSDT",
    "UBUSDT", "UMAUSDT", "UNIUSDT", "USDCUSDT", "USELESSUSDT",
    "USTCUSDT", "USUALUSDT", "USUSDT", "VANAUSDT", "VANRYUSDT",
    "VELODROMEUSDT", "VELVETUSDT", "VETUSDT", "VFYUSDT", "VICUSDT",
    "VINEUSDT", "VIRTUALUSDT", "VTHOUSDT", "VVVUSDT", "WALUSDT",
    "WAXPUSDT", "WCTUSDT", "WETUSDT", "WIFUSDT", "WLDUSDT",
    "WLFIUSDT", "WOOUSDT", "WUSDT", "XAIUSDT", "XANUSDT",
    "XLMUSDT", "XMRUSDT", "XNYUSDT", "XPINUSDT", "XPLUSDT",
    "XRPUSDT", "XTZUSDT", "XVGUSDT", "XVSUSDT", "YALAUSDT",
    "YBUSDT", "YFIUSDT", "YGGUSDT", "ZBTUSDT", "ZECUSDT",
    "ZENUSDT", "ZEREBROUSDT", "ZETAUSDT", "ZILUSDT", "ZKCUSDT",
    "ZKJUSDT", "ZKPUSDT", "ZKUSDT", "ZORAUSDT", "ZRCUSDT",
    "ZROUSDT", "ZRXUSDT",
]


DEFAULT_HISTORY_TIMEFRAMES: List[str] = ["5m", "15m", "1h", "4h", "1d", "1w"]
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

# --- Rally System (Fast15) ---
# Rally Oracle v1 - GOLDEN_77 Baseline
# This path references the preserved 77-rally baseline for SOL 15m.
# READ-ONLY: This file should NEVER be overwritten by any process.
GOLDEN_FAST15_SOL_77_PATH = 'library/fast15_rallies/SOLUSDT/fast15_rallies_GOLDEN_77rallies_max_lookback300.parquet'

# --- Fast15 Rally Scanner Settings ---
FAST15_RALLY_TF: str = "15m"
FAST15_LOOKAHEAD_BARS: int = 21  # 1-21 bars lookahead window
FAST15_RALLY_BUCKETS: tuple[float, ...] = (0.00, 0.05, 0.10, 0.20, 0.30)  # 0%, 5%, 10%, 20%, 30% (IRON, BRONZE, SILVER, GOLD, DIAMOND)
FAST15_MIN_GAIN: float = 0.00  # Minimum 0% gain - includes IRON tier
FAST15_EVENT_GAP: int = 3  # Minimum 3 bars between events to prevent overlap

# MACD Phase classification thresholds for Fast15
FAST15_MACD_SLEEP_THRESHOLD: float = 0.0005  # Very small histogram = sleep
FAST15_MACD_WAKE_THRESHOLD: float = 0.001    # Rising from sleep = awakening
FAST15_MACD_RUN_THRESHOLD: float = 0.003     # Strong positive momentum = running


# --- Time-Labs v1 Settings ---
TIME_LABS_TFS: List[str] = ["5m", "1h", "4h"]

TIME_LABS_LOOKAHEAD_BARS: Dict[str, int] = {
    "5m": 12,  # 1 hour window
    "1h": 10,  # 1-10 bars window (~10 hours)
    "4h": 10,  # 1-10 bars window (~40 hours)
}

TIME_LABS_RALLY_BUCKETS: List[float] = [0.00, 0.05, 0.10, 0.20, 0.30]  # 0%, 5%, 10%, 20%, 30% (IRON, BRONZE, SILVER, GOLD, DIAMOND)

TIME_LABS_MIN_GAIN: Dict[str, float] = {
    "5m": 0.03,  # 3% for 5m to catch micro-rallies
    "1h": 0.05,  # 5%
    "4h": 0.07,  # 7%
}

TIME_LABS_EVENT_GAP: Dict[str, int] = {
    "5m": 5,
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
