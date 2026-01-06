"""
Strategy Scanner
================

Backend logic for the Strategy Studio module.
Scans coins with user-defined formulas and returns matching events.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.history_service import load_existing_history
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyEvent:
    """A single event matching the strategy criteria."""
    symbol: str
    event_time: pd.Timestamp
    event_idx: int
    gain_pct: float
    tier: str
    volume_ratio: float
    # Pre-conditions at event
    rsi: float
    macd_hist: float
    bb_position: float
    ema_aligned: str


@dataclass
class StrategyScanResult:
    """Result of a strategy scan."""
    total_events: int = 0
    diamond_count: int = 0
    gold_count: int = 0
    silver_count: int = 0
    bronze_count: int = 0
    avg_gain: float = 0.0
    events: List[StrategyEvent] = field(default_factory=list)
    events_df: Optional[pd.DataFrame] = None


# Available conditions
AVAILABLE_CONDITIONS = {
    'RSI_50_70': {
        'label': 'RSI 50-70',
        'description': 'RSI değeri 50-70 arasında',
        'default': True,
    },
    'MACD_POSITIVE': {
        'label': 'MACD Pozitif',
        'description': 'MACD histogram sıfırın üstünde',
        'default': True,
    },
    'EMA_BULLISH': {
        'label': 'EMA Bullish (9>21>50)',
        'description': 'EMA\'lar boğa sıralamasında',
        'default': False,
    },
    'PRICE_ABOVE_EMA50': {
        'label': 'Fiyat > EMA50',
        'description': 'Fiyat EMA50\'nin üzerinde',
        'default': False,
    },
    'BB_MIDDLE': {
        'label': 'BB Orta (0.3-0.7)',
        'description': 'Bollinger pozisyonu orta bölgede',
        'default': False,
    },
    'RSI_ABOVE_EMA': {
        'label': 'RSI > RSI-EMA',
        'description': 'RSI, RSI-EMA\'nın üstünde',
        'default': False,
    },
    'MACD_RISING': {
        'label': 'MACD Yükseliyor',
        'description': 'MACD histogram artış trendinde',
        'default': False,
    },
    'GREEN_CANDLES_3': {
        'label': '3 Yeşil Mum',
        'description': 'İlk 3 mum yeşil',
        'default': True,
    },
}


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all technical indicators needed for strategy evaluation."""
    df = df.copy()
    
    # RSI (14 period)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # RSI EMA (11 period)
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # EMAs
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Bollinger Bands
    df['bb_mid'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Volume
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    
    return df


def get_tier(gain_pct: float) -> str:
    """Determine tier based on gain percentage."""
    if gain_pct >= 30:
        return 'DIAMOND'
    elif gain_pct >= 20:
        return 'GOLD'
    elif gain_pct >= 15:
        return 'SILVER'
    elif gain_pct >= 10:
        return 'BRONZE'
    else:
        return 'IRON'


def get_ema_alignment(close: float, ema9: float, ema21: float, ema50: float) -> str:
    """Get EMA alignment status."""
    if close > ema9 > ema21 > ema50:
        return 'BULLISH'
    elif close < ema9 < ema21 < ema50:
        return 'BEARISH'
    else:
        return 'MIXED'


def evaluate_conditions(
    df: pd.DataFrame, 
    idx: int,
    conditions: Dict[str, bool],
    lookback: int = 5
) -> bool:
    """
    Evaluate if all enabled conditions are met at the given index.
    Looks back `lookback` bars for pre-conditions.
    """
    if idx < lookback or idx >= len(df):
        return False
    
    pre = df.iloc[idx - lookback: idx]
    bar = df.iloc[idx]
    
    # Use the bar just before the event for conditions
    pre_bar = df.iloc[idx - 1]
    
    for cond_name, is_enabled in conditions.items():
        if not is_enabled:
            continue
        
        try:
            if cond_name == 'RSI_50_70':
                if not (50 <= pre_bar['rsi'] <= 70):
                    return False
                    
            elif cond_name == 'MACD_POSITIVE':
                if pre_bar['macd_hist'] <= 0:
                    return False
                    
            elif cond_name == 'EMA_BULLISH':
                if not (pre_bar['ema9'] > pre_bar['ema21'] > pre_bar['ema50']):
                    return False
                    
            elif cond_name == 'PRICE_ABOVE_EMA50':
                if pre_bar['close'] <= pre_bar['ema50']:
                    return False
                    
            elif cond_name == 'BB_MIDDLE':
                if not (0.3 <= pre_bar['bb_position'] <= 0.7):
                    return False
                    
            elif cond_name == 'RSI_ABOVE_EMA':
                if pre_bar['rsi'] <= pre_bar['rsi_ema']:
                    return False
                    
            elif cond_name == 'MACD_RISING':
                if len(pre) >= 3:
                    if pre['macd_hist'].iloc[-1] <= pre['macd_hist'].iloc[-3]:
                        return False
                        
            elif cond_name == 'GREEN_CANDLES_3':
                if idx + 2 >= len(df):
                    return False
                c1_green = df['close'].iloc[idx] > df['open'].iloc[idx]
                c2_green = df['close'].iloc[idx+1] > df['open'].iloc[idx+1]
                c3_green = df['close'].iloc[idx+2] > df['open'].iloc[idx+2]
                if not (c1_green and c2_green and c3_green):
                    return False
                    
        except (KeyError, IndexError):
            return False
    
    return True


def scan_with_formula(
    coins: List[str],
    timeframe: str,
    conditions: Dict[str, bool],
    min_volume_ratio: float = 7.0,
    min_gain_pct: float = 10.0,
    progress_callback=None
) -> StrategyScanResult:
    """
    Scan coins with the given conditions.
    
    Args:
        coins: List of symbols to scan
        timeframe: Timeframe to use (15m, 1h, 4h)
        conditions: Dict of condition_name -> is_enabled
        min_volume_ratio: Minimum volume ratio to trigger
        min_gain_pct: Minimum gain percentage for events
        progress_callback: Optional callback(current, total) for progress
    
    Returns:
        StrategyScanResult with matching events
    """
    result = StrategyScanResult()
    all_events = []
    
    for i, symbol in enumerate(coins):
        if progress_callback:
            progress_callback(i, len(coins))
        
        df = load_existing_history(symbol, timeframe)
        if df is None or len(df) < 100:
            continue
        
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        df = calculate_indicators(df)
        
        for idx in range(60, len(df) - 3):
            # Volume spike check
            if df['volume_ratio'].iloc[idx] < min_volume_ratio:
                continue
            
            # Evaluate all conditions
            if not evaluate_conditions(df, idx, conditions):
                continue
            
            # Calculate gain (3 bar forward)
            entry = df['open'].iloc[idx]
            exit_price = df['close'].iloc[idx + 2] if idx + 2 < len(df) else df['close'].iloc[idx]
            gain_pct = (exit_price - entry) / entry * 100
            
            if gain_pct < min_gain_pct:
                continue
            
            tier = get_tier(gain_pct)
            
            event = StrategyEvent(
                symbol=symbol,
                event_time=df['datetime'].iloc[idx],
                event_idx=idx,
                gain_pct=gain_pct,
                tier=tier,
                volume_ratio=df['volume_ratio'].iloc[idx],
                rsi=df['rsi'].iloc[idx - 1],
                macd_hist=df['macd_hist'].iloc[idx - 1],
                bb_position=df['bb_position'].iloc[idx - 1],
                ema_aligned=get_ema_alignment(
                    df['close'].iloc[idx - 1],
                    df['ema9'].iloc[idx - 1],
                    df['ema21'].iloc[idx - 1],
                    df['ema50'].iloc[idx - 1]
                )
            )
            all_events.append(event)
    
    # Calculate summary
    result.events = all_events
    result.total_events = len(all_events)
    
    if all_events:
        result.diamond_count = sum(1 for e in all_events if e.tier == 'DIAMOND')
        result.gold_count = sum(1 for e in all_events if e.tier == 'GOLD')
        result.silver_count = sum(1 for e in all_events if e.tier == 'SILVER')
        result.bronze_count = sum(1 for e in all_events if e.tier == 'BRONZE')
        result.avg_gain = sum(e.gain_pct for e in all_events) / len(all_events)
        
        # Convert to DataFrame for easier handling
        result.events_df = pd.DataFrame([
            {
                'symbol': e.symbol,
                'event_time': e.event_time,
                'event_idx': e.event_idx,
                'gain_pct': e.gain_pct,
                'tier': e.tier,
                'volume_ratio': e.volume_ratio,
                'rsi': e.rsi,
                'macd_hist': e.macd_hist,
                'bb_position': e.bb_position,
                'ema_aligned': e.ema_aligned,
            }
            for e in all_events
        ])
    
    return result


def get_events_for_symbol(result: StrategyScanResult, symbol: str) -> pd.DataFrame:
    """Get events for a specific symbol from scan result."""
    if result.events_df is None or result.events_df.empty:
        return pd.DataFrame()
    
    return result.events_df[result.events_df['symbol'] == symbol].copy()


def get_unique_symbols(result: StrategyScanResult) -> List[str]:
    """Get list of unique symbols from scan result."""
    if result.events_df is None or result.events_df.empty:
        return []
    
    return sorted(result.events_df['symbol'].unique().tolist())
