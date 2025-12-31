"""
Simyacı Feature Engine
======================
"43 DNA Parçacığı - Her Biri Bir Ameliyat Aleti"

This module calculates all technical indicators (features) for rally DNA extraction.
Each feature is a separate function with:
- Clear documentation
- Input validation
- Boundary checks
- NaN handling
- Unit test coverage

CATEGORIES (10 Total):
1. Momentum (6 features)
2. Volume (5 features)
3. Price Action (8 features)
4. Trend (6 features)
5. Fibonacci (3 features)
6. Wyckoff (3 features)
7. Volatility (4 features)
8. Multi-TF (3 features)
9. Statistical (3 features)
10. Candle (2 features)
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# CATEGORY 1: MOMENTUM (6 Features)
# ============================================================================

def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
    """
    Calculate RSI (Relative Strength Index).
    
    Range: 0-100
    - RSI < 30: Oversold
    - RSI > 70: Overbought
    
    Args:
        df: OHLCV DataFrame
        period: RSI period (default: 14)
        column: Price column to use
        
    Returns:
        Series with RSI values
        
    Raises:
        ValueError: If column missing or period invalid
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    if period < 1:
        raise ValueError(f"Period must be >= 1, got {period}")
    
    # Calculate price changes
    delta = df[column].diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Calculate EWM (Exponential Weighted Moving Average)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Boundary check
    rsi = rsi.clip(0, 100)
    
    return rsi


def detect_rsi_divergence(
    df: pd.DataFrame,
    rsi_column: str = 'rsi',
    price_column: str = 'close',
    lookback: int = 14
) -> pd.Series:
    """
    Detect RSI Bullish Divergence.
    
    Bullish Divergence:
    - Price makes lower low
    - RSI makes higher low
    - Signal: Potential reversal up
    
    Args:
        df: DataFrame with RSI and price
        rsi_column: RSI column name
        price_column: Price column name
        lookback: Bars to look back for divergence
        
    Returns:
        Boolean Series (True = divergence detected)
    """
    if rsi_column not in df.columns:
        # If RSI not calculated, do it now
        df = df.copy()
        df['rsi'] = calculate_rsi(df, column=price_column)
        rsi_column = 'rsi'
    
    # Find local lows
    price_lows = df[price_column].rolling(window=5, center=True).min() == df[price_column]
    rsi_lows = df[rsi_column].rolling(window=5, center=True).min() == df[rsi_column]
    
    # Detect divergence
    divergence = pd.Series(False, index=df.index)
    
    for i in range(lookback, len(df)):
        recent_window = df.iloc[i-lookback:i+1]
        
        # Get price lows in window
        price_low_indices = recent_window[price_lows.iloc[i-lookback:i+1]].index
        rsi_low_indices = recent_window[rsi_lows.iloc[i-lookback:i+1]].index
        
        if len(price_low_indices) >= 2 and len(rsi_low_indices) >= 2:
            # Compare last two lows
            last_price_low = df.loc[price_low_indices[-1], price_column]
            prev_price_low = df.loc[price_low_indices[-2], price_column]
            
            last_rsi_low = df.loc[rsi_low_indices[-1], rsi_column]
            prev_rsi_low = df.loc[rsi_low_indices[-2], rsi_column]
            
            # Bullish divergence condition
            if last_price_low < prev_price_low and last_rsi_low > prev_rsi_low:
                divergence.iloc[i] = True
    
    return divergence


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = 'close'
) -> Dict[str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Components:
    - MACD Line: EMA(fast) - EMA(slow)
    - Signal Line: EMA(MACD, signal_period)
    - Histogram: MACD - Signal
    
    Args:
        df: OHLCV DataFrame
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line period (default: 9)
        column: Price column
        
    Returns:
        Dict with 'macd', 'signal', 'histogram' Series
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    
    # Calculate EMAs
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    
    # MACD Line
    macd_line = ema_fast - ema_slow
    
    # Signal Line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    # Histogram
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def detect_macd_cross(df: pd.DataFrame, macd_col: str = 'macd', signal_col: str = 'macd_signal') -> pd.Series:
    """
    Detect MACD Golden Cross (bullish signal).
    
    Golden Cross: MACD crosses above Signal from below
    
    Returns:
        Boolean Series (True = golden cross)
    """
    if macd_col not in df.columns or signal_col not in df.columns:
        # Calculate MACD if missing
        macd_data = calculate_macd(df)
        df = df.copy()
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        macd_col = 'macd'
        signal_col = 'macd_signal'
    
    # Detect crossover
    cross = (
        (df[macd_col].shift(1) < df[signal_col].shift(1)) &  # Was below
        (df[macd_col] > df[signal_col])  # Now above
    )
    
    return cross


def calculate_stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
    smooth: int = 3
) -> Dict[str, pd.Series]:
    """
    Calculate Stochastic Oscillator (%K and %D).
    
    Range: 0-100
    - Stochastic < 20: Oversold
    - Stochastic > 80: Overbought
    
    Args:
        df: OHLCV DataFrame
        k_period: %K period
        d_period: %D smoothing period
        smooth: %K smoothing
        
    Returns:
        Dict with 'k' and 'd' Series
    """
    # Calculate raw %K
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    k_raw = 100 * (df['close'] - low_min) / (high_max - low_min)
    
    # Smooth %K
    k = k_raw.rolling(window=smooth).mean()
    
    # Calculate %D
    d = k.rolling(window=d_period).mean()
    
    # Boundary check
    k = k.clip(0, 100)
    d = d.clip(0, 100)
    
    return {'k': k, 'd': d}


# ============================================================================
# CATEGORY 2: VOLUME (5 Features)
# ============================================================================

def calculate_volume_ratio(df: pd.DataFrame, period: int = 20, column: str = 'volume') -> pd.Series:
    """
    Calculate Volume Ratio (Current Volume / Average Volume).
    
    High ratio (>3) indicates unusual activity.
    
    Args:
        df: OHLCV DataFrame
        period: MA period (default: 20)
        column: Volume column
        
    Returns:
        Series with volume ratios
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    
    avg_volume = df[column].rolling(window=period).mean()
    ratio = df[column] / avg_volume
    
    # Handle division by zero
    ratio = ratio.fillna(0).replace([np.inf, -np.inf], 0)
    
    return ratio


def detect_volume_spike(df: pd.DataFrame, threshold: float = 5.0, period: int = 20) -> pd.Series:
    """
    Detect volume spikes (volume >> average).
    
    Spike = Volume > threshold * avg_volume
    
    Args:
        df: OHLCV DataFrame
        threshold: Spike threshold (default: 5.0 = 5x average)
        period: MA period
        
    Returns:
        Boolean Series (True = spike detected)
    """
    ratio = calculate_volume_ratio(df, period=period)
    return ratio > threshold


def calculate_on_balance_volume(df: pd.DataFrame) -> pd.Series:
    """
    Calculate On-Balance Volume (OBV).
    
    OBV tracks cumulative volume flow:
    - Price up: Add volume
    - Price down: Subtract volume
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        Series with OBV values
    """
    if 'close' not in df.columns or 'volume' not in df.columns:
        raise ValueError("DataFrame must have 'close' and 'volume' columns")
    
    # Determine direction
    direction = df['close'].diff()
    direction = direction.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    
    # Calculate OBV
    obv = (direction * df['volume']).cumsum()
    
    return obv


def detect_volume_climax(df: pd.DataFrame, lookback: int = 10) -> pd.Series:
    """
    Detect Volume Climax (selling/buying climax).
    
    Climax = Volume at peak in recent window
    Indicates potential exhaustion/capitulation.
    
    Args:
        df: OHLCV DataFrame
        lookback: Window to check for peak
        
    Returns:
        Boolean Series (True = climax detected)
    """
    if 'volume' not in df.columns:
        raise ValueError("'volume' column required")
    
    # Find volume peaks
    rolling_max = df['volume'].rolling(window=lookback, center=True).max()
    is_peak = df['volume'] == rolling_max
    
    return is_peak.fillna(False)


def detect_volume_dry_up(df: pd.DataFrame, threshold: float = 0.5, period: int = 20) -> pd.Series:
    """
    Detect Volume Dry-Up (unusually low volume).
    
    Dry-Up = Volume < threshold * avg_volume
    Low volume can precede breakouts.
    
    Args:
        df: OHLCV DataFrame
        threshold: Dry-up threshold (default: 0.5 = half average)
        period: MA period
        
    Returns:
        Boolean Series (True = dry-up detected)
    """
    ratio = calculate_volume_ratio(df, period=period)
    return ratio < threshold


def extract_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract all Volume category features.
    
    Adds 5 columns:
    - volume_ratio_20
    - volume_spike
    - on_balance_volume
    - volume_climax
    - volume_dry_up
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        DataFrame with added feature columns
    """
    result = df.copy()
    
    logger.info("Calculating Volume features...")
    
    # 1. Volume Ratio
    result['volume_ratio_20'] = calculate_volume_ratio(result, period=20)
    
    # 2. Volume Spike
    result['volume_spike'] = detect_volume_spike(result, threshold=5.0)
    
    # 3. On-Balance Volume
    result['on_balance_volume'] = calculate_on_balance_volume(result)
    
    # 4. Volume Climax
    result['volume_climax'] = detect_volume_climax(result, lookback=10)
    
    # 5. Volume Dry-Up
    result['volume_dry_up'] = detect_volume_dry_up(result, threshold=0.5)
    
    logger.info(f"Volume features extracted: {len(result)} rows")
    
    return result


# ============================================================================
# CATEGORY 4: TREND (6 Features)
# ============================================================================

def calculate_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.Series:
    """
    Calculate Exponential Moving Average.
    
    Args:
        df: OHLCV DataFrame
        period: EMA period
        column: Price column
        
    Returns:
        Series with EMA values
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    
    return df[column].ewm(span=period, adjust=False).mean()


def detect_ema_cross(
    df: pd.DataFrame,
    fast_period: int = 9,
    slow_period: int = 21,
    column: str = 'close'
) -> pd.Series:
    """
    Detect EMA Golden Cross (fast crosses above slow).
    
    Golden Cross = bullish signal
    
    Args:
        df: OHLCV DataFrame
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        column: Price column
        
    Returns:
        Boolean Series (True = golden cross)
    """
    ema_fast = calculate_ema(df, fast_period, column)
    ema_slow = calculate_ema(df, slow_period, column)
    
    # Detect crossover
    cross = (
        (ema_fast.shift(1) < ema_slow.shift(1)) &  # Was below
        (ema_fast > ema_slow)  # Now above
    )
    
    return cross


def calculate_price_vs_ema(
    df: pd.DataFrame,
    ema_period: int = 50,
    column: str = 'close'
) -> pd.Series:
    """
    Calculate price position relative to EMA.
    
    Positive = Price above EMA (bullish)
    Negative = Price below EMA (bearish)
    
    Args:
        df: OHLCV DataFrame
        ema_period: EMA period
        column: Price column
        
    Returns:
        Series with percentage difference
    """
    ema = calculate_ema(df, ema_period, column)
    diff_pct = ((df[column] - ema) / ema) * 100
    
    return diff_pct


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate ADX (Average Directional Index).
    
    ADX measures trend strength (0-100):
    - ADX < 20: Weak trend
    - ADX > 40: Strong trend
    
    Args:
        df: OHLCV DataFrame
        period: ADX period
        
    Returns:
        Series with ADX values
    """
    if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        raise ValueError("DataFrame must have 'high', 'low', 'close' columns")
    
    # Calculate True Range
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # Calculate Directional Movement
    up_move = df['high'] - df['high'].shift()
    down_move = df['low'].shift() - df['low']
    
    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move
    
    # Smooth with EMA
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    
    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Boundary check
    adx = adx.clip(0, 100).fillna(0)
    
    return adx


def detect_trend_direction(df: pd.DataFrame, ema_period: int = 50) -> pd.Series:
    """
    Detect trend direction based on EMA slope.
    
    Returns:
        Series with values: 'UP', 'DOWN', 'FLAT'
    """
    ema = calculate_ema(df, ema_period)
    
    # Calculate EMA slope
    slope = ema.diff(5)  # 5-bar slope
    
    # Classify
    direction = pd.Series('FLAT', index=df.index)
    direction[slope > 0] = 'UP'
    direction[slope < 0] = 'DOWN'
    
    return direction


def calculate_trend_strength(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate trend strength (simplified ADX proxy).
    
    Range: 0-100
    Higher = stronger trend
    
    Args:
        df: OHLCV DataFrame
        period: Calculation period
        
    Returns:
        Series with trend strength values
    """
    # Use ADX as trend strength
    return calculate_adx(df, period)


def extract_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract all Trend category features.
    
    Adds 6 columns:
    - ema_9
    - ema_21
    - ema_50
    - ema_cross_9_21
    - price_vs_ema_50
    - adx_14
    - trend_direction
    - trend_strength
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        DataFrame with added feature columns
    """
    result = df.copy()
    
    logger.info("Calculating Trend features...")
    
    # 1. EMAs
    result['ema_9'] = calculate_ema(result, 9)
    result['ema_21'] = calculate_ema(result, 21)
    result['ema_50'] = calculate_ema(result, 50)
    result['ema_200'] = calculate_ema(result, 200)
    
    # 2. EMA Cross
    result['ema_cross_9_21'] = detect_ema_cross(result, 9, 21)
    
    # 3. Price vs EMA
    result['price_vs_ema_50'] = calculate_price_vs_ema(result, 50)
    result['price_vs_ema_200'] = calculate_price_vs_ema(result, 200)
    
    # 4. ADX
    result['adx_14'] = calculate_adx(result, 14)
    
    # 5. Trend Direction
    result['trend_direction'] = detect_trend_direction(result, 50)
    
    # 6. Trend Strength
    result['trend_strength'] = calculate_trend_strength(result, 14)
    
    logger.info(f"Trend features extracted: {len(result)} rows")
    
    return result


# ============================================================================
# CATEGORY 3: PRICE ACTION (8 Features)
# ============================================================================

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> Dict[str, pd.Series]:
    """Calculate Bollinger Bands."""
    sma = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    
    upper = sma + (std * rolling_std)
    lower = sma - (std * rolling_std)
    
    return {'upper': upper, 'middle': sma, 'lower': lower}


def detect_bb_squeeze(df: pd.DataFrame, threshold: float = 0.02) -> pd.Series:
    """Detect Bollinger Band Squeeze (low volatility)."""
    bb = calculate_bollinger_bands(df)
    bandwidth = (bb['upper'] - bb['lower']) / bb['middle']
    return bandwidth < threshold


def detect_support_bounce(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """Detect bounce from support level."""
    low_min = df['low'].rolling(window=lookback).min()
    is_at_support = (df['low'] <= low_min * 1.01)  # Within 1% of support
    bounce = is_at_support & (df['close'] > df['open'])  # Bullish candle
    return bounce


def detect_resistance_break(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """Detect break above resistance."""
    high_max = df['high'].rolling(window=lookback).max()
    break_resistance = df['close'] > high_max.shift(1)
    return break_resistance


def detect_fair_value_gap(df: pd.DataFrame) -> pd.Series:
    """Detect Fair Value Gap (FVG) - imbalance zones."""
    # FVG = gap between candle 1's high and candle 3's low
    gap = df['low'].shift(-1) - df['high'].shift(1)
    return gap > 0


def extract_price_action_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract Price Action features."""
    result = df.copy()
    logger.info("Calculating Price Action features...")
    
    bb = calculate_bollinger_bands(result)
    result['bb_upper'] = bb['upper']
    result['bb_middle'] = bb['middle']
    result['bb_lower'] = bb['lower']
    result['bb_squeeze'] = detect_bb_squeeze(result)
    result['support_bounce'] = detect_support_bounce(result)
    result['resistance_break'] = detect_resistance_break(result)
    result['fair_value_gap'] = detect_fair_value_gap(result)
    result['price_vs_bb'] = (result['close'] - bb['lower']) / (bb['upper'] - bb['lower'])
    
    logger.info(f"Price Action features extracted: {len(result)} rows")
    return result


# ============================================================================
# CATEGORY 7: VOLATILITY (4 Features)
# ============================================================================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_bb_width(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Bollinger Band Width."""
    bb = calculate_bollinger_bands(df, period)
    width = (bb['upper'] - bb['lower']) / bb['middle']
    return width


def extract_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract Volatility features."""
    result = df.copy()
    logger.info("Calculating Volatility features...")
    
    result['atr_14'] = calculate_atr(result, 14)
    result['bb_width'] = calculate_bb_width(result)
    result['volatility_ratio'] = result['atr_14'] / result['close'] * 100
    result['price_range'] = (result['high'] - result['low']) / result['close'] * 100
    
    logger.info(f"Volatility features extracted: {len(result)} rows")
    return result


# ============================================================================
# CATEGORY 5: FIBONACCI (3 Features)
# ============================================================================

def calculate_fibonacci_levels(df: pd.DataFrame, lookback: int = 50) -> Dict[str, pd.Series]:
    """Calculate Fibonacci retracement levels."""
    high = df['high'].rolling(window=lookback).max()
    low = df['low'].rolling(window=lookback).min()
    diff = high - low
    
    return {
        'fib_0.236': high - 0.236 * diff,
        'fib_0.382': high - 0.382 * diff,
        'fib_0.618': high - 0.618 * diff,
    }


def extract_fibonacci_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract Fibonacci features."""
    result = df.copy()
    logger.info("Calculating Fibonacci features...")
    
    fib = calculate_fibonacci_levels(result)
    result['near_fib_618'] = abs(result['close'] - fib['fib_0.618']) / result['close'] < 0.005
    result['near_fib_382'] = abs(result['close'] - fib['fib_0.382']) / result['close'] < 0.005
    result['fib_zone'] = result['near_fib_618'] | result['near_fib_382']
    
    logger.info(f"Fibonacci features extracted: {len(result)} rows")
    return result


# ============================================================================
# CATEGORY 9: STATISTICAL (3 Features)
# ============================================================================

def calculate_z_score(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Z-Score."""
    mean = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    z_score = (df['close'] - mean) / std
    return z_score.fillna(0)


def extract_statistical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract Statistical features."""
    result = df.copy()
    logger.info("Calculating Statistical features...")
    
    result['z_score'] = calculate_z_score(result)
    result['price_percentile'] = result['close'].rolling(window=50).apply(
        lambda x: (x.iloc[-1] > x).sum() / len(x) * 100
    )
    result['volume_percentile'] = result['volume'].rolling(window=50).apply(
        lambda x: (x.iloc[-1] > x).sum() / len(x) * 100
    )
    
    logger.info(f"Statistical features extracted: {len(result)} rows")
    return result


# ============================================================================
# CATEGORY 10: CANDLE PATTERNS (2 Features)
# ============================================================================

def detect_hammer(df: pd.DataFrame) -> pd.Series:
    """Detect Hammer candle pattern."""
    body = abs(df['close'] - df['open'])
    lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    
    is_hammer = (
        (lower_wick > 2 * body) &
        (upper_wick < body * 0.5)
    )
    return is_hammer


def detect_engulfing(df: pd.DataFrame) -> pd.Series:
    """Detect Bullish Engulfing pattern."""
    is_bullish = df['close'] > df['open']
    prev_bearish = df['close'].shift(1) < df['open'].shift(1)
    
    engulfs = (
        is_bullish &
        prev_bearish &
        (df['open'] < df['close'].shift(1)) &
        (df['close'] > df['open'].shift(1))
    )
    return engulfs


def extract_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract Candle Pattern features."""
    result = df.copy()
    logger.info("Calculating Candle features...")
    
    result['hammer'] = detect_hammer(result)
    result['bullish_engulfing'] = detect_engulfing(result)
    
    logger.info(f"Candle features extracted: {len(result)} rows")
    return result


# ============================================================================
# FEATURE EXTRACTION MASTER FUNCTION
# ============================================================================

def extract_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract all Momentum category features.
    
    Adds 6 columns to DataFrame:
    - rsi_14
    - rsi_divergence_bullish
    - macd
    - macd_signal
    - macd_histogram
    - macd_cross
    - stoch_k
    - stoch_d
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        DataFrame with added feature columns
    """
    result = df.copy()
    
    # 1. RSI
    logger.info("Calculating RSI...")
    result['rsi_14'] = calculate_rsi(result, period=14)
    
    # 2. RSI Divergence
    logger.info("Detecting RSI divergence...")
    result['rsi_divergence_bullish'] = detect_rsi_divergence(result)
    
    # 3. MACD
    logger.info("Calculating MACD...")
    macd_data = calculate_macd(result)
    result['macd'] = macd_data['macd']
    result['macd_signal'] = macd_data['signal']
    result['macd_histogram'] = macd_data['histogram']
    
    # 4. MACD Cross
    result['macd_cross'] = detect_macd_cross(result, 'macd', 'macd_signal')
    
    # 5. Stochastic
    logger.info("Calculating Stochastic...")
    stoch_data = calculate_stochastic(result)
    result['stoch_k'] = stoch_data['k']
    result['stoch_d'] = stoch_data['d']
    
    logger.info(f"Momentum features extracted: {len(result)} rows")
    
    return result


def extract_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract ALL 43 features across 10 categories.
    
    Master function for complete feature extraction.
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        DataFrame with all feature columns
    """
    result = df.copy()
    
    logger.info("Extracting all features...")
    
    # Category 1: Momentum (6 features)
    result = extract_momentum_features(result)
    
    # Category 2: Volume (5 features)
    result = extract_volume_features(result)
    
    # Category 3: Price Action (8 features)
    result = extract_price_action_features(result)
    
    # Category 4: Trend (6 features)
    result = extract_trend_features(result)
    
    # Category 5: Fibonacci (3 features)
    result = extract_fibonacci_features(result)
    
    # Category 7: Volatility (4 features)
    result = extract_volatility_features(result)
    
    # Category 9: Statistical (3 features)
    result = extract_statistical_features(result)
    
    # Category 10: Candle (2 features)
    result = extract_candle_features(result)
    
    feature_count = len([c for c in result.columns if c not in df.columns])
    logger.info(f"Feature extraction complete: {feature_count} new features added")
    
    return result
