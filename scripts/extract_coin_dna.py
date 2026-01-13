#!/usr/bin/env python3
"""
Coin DNA Extractor - Comprehensive behavioral profiling for all coins.
Extracts features across multiple timeframes to classify coins by behavior.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d']

def compute_atr(df, period=14):
    """Compute Average True Range percentage."""
    if len(df) < period + 1:
        return np.nan, np.nan
    
    tr = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    atr = tr.rolling(period).mean()
    atr_pct = (atr / df['close']) * 100
    
    avg_atr = atr_pct.mean()
    atr_var = atr_pct.std()
    
    return avg_atr, atr_var

def compute_wick_metrics(df):
    """Compute wick/needle metrics."""
    if df.empty:
        return {}
    
    # Body size
    body = abs(df['close'] - df['open'])
    
    # Upper wick
    upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    
    # Lower wick
    lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    
    # Total wick
    total_wick = upper_wick + lower_wick
    
    # Avoid division by zero
    body_safe = body.replace(0, 0.0001)
    
    # Wick to body ratio
    wick_ratio = total_wick / body_safe
    
    # Needle detection (wick > 3x body)
    is_needle = wick_ratio > 3
    needle_freq = is_needle.sum() / len(df) if len(df) > 0 else 0
    
    # Upper vs lower wick dominance
    upper_dominant = (upper_wick > lower_wick * 2).sum() / len(df) if len(df) > 0 else 0
    lower_dominant = (lower_wick > upper_wick * 2).sum() / len(df) if len(df) > 0 else 0
    
    return {
        'avg_wick_ratio': wick_ratio.mean(),
        'needle_freq': needle_freq,
        'upper_wick_dominance': upper_dominant,
        'lower_wick_dominance': lower_dominant
    }

def compute_rally_metrics(df):
    """Compute rally-related metrics."""
    if len(df) < 20:
        return {}
    
    # Rolling returns
    returns = df['close'].pct_change()
    
    # Max single move
    max_up = returns.max() * 100
    max_down = returns.min() * 100
    
    # Rally detection (10%+ gain in rolling window)
    rolling_10 = df['close'].pct_change(10) * 100
    rallies_10pct = (rolling_10 > 10).sum()
    
    # Rally frequency per 1000 bars
    rally_freq = (rallies_10pct / len(df)) * 1000 if len(df) > 0 else 0
    
    return {
        'max_up_move': max_up,
        'max_down_move': abs(max_down),
        'rally_freq_per_1000': rally_freq
    }

def compute_rsi(close, period=14):
    """Compute RSI."""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.0001)
    return 100 - (100 / (1 + rs))

def compute_momentum_metrics(df):
    """Compute momentum-related metrics."""
    if len(df) < 30:
        return {}
    
    rsi = compute_rsi(df['close'])
    
    # Overbought/oversold frequency
    overbought_freq = (rsi > 70).sum() / len(rsi) if len(rsi) > 0 else 0
    oversold_freq = (rsi < 30).sum() / len(rsi) if len(rsi) > 0 else 0
    
    # Average RSI
    avg_rsi = rsi.mean()
    
    # RSI volatility
    rsi_volatility = rsi.std()
    
    return {
        'avg_rsi': avg_rsi,
        'rsi_volatility': rsi_volatility,
        'overbought_freq': overbought_freq,
        'oversold_freq': oversold_freq
    }

def compute_volume_metrics(df):
    """Compute volume-related metrics."""
    if len(df) < 20 or 'volume' not in df.columns:
        return {}
    
    vol = df['volume']
    
    # Volume consistency
    vol_mean = vol.mean()
    vol_std = vol.std()
    vol_cv = vol_std / vol_mean if vol_mean > 0 else 0
    
    # Volume spike detection (3x average)
    vol_spikes = (vol > vol_mean * 3).sum()
    spike_freq = vol_spikes / len(df) if len(df) > 0 else 0
    
    # Volume trend (increasing or decreasing)
    vol_change = vol.pct_change().mean()
    
    return {
        'volume_cv': vol_cv,
        'volume_spike_freq': spike_freq,
        'volume_trend': vol_change
    }

def extract_features_for_timeframe(symbol, tf):
    """Extract all features for a single timeframe."""
    path = coin_cell_paths.get_history_file(symbol, tf)
    
    if not path.exists():
        return None
    
    try:
        df = pd.read_parquet(path)
        if len(df) < 50:
            return None
        
        features = {'symbol': symbol, 'timeframe': tf}
        
        # ATR metrics
        avg_atr, atr_var = compute_atr(df)
        features['avg_atr_pct'] = avg_atr
        features['atr_variance'] = atr_var
        
        # Wick metrics
        wick_metrics = compute_wick_metrics(df)
        features.update(wick_metrics)
        
        # Rally metrics
        rally_metrics = compute_rally_metrics(df)
        features.update(rally_metrics)
        
        # Momentum metrics
        momentum_metrics = compute_momentum_metrics(df)
        features.update(momentum_metrics)
        
        # Volume metrics
        volume_metrics = compute_volume_metrics(df)
        features.update(volume_metrics)
        
        # Data quality
        features['bar_count'] = len(df)
        
        return features
        
    except Exception as e:
        logger.error(f"Error processing {symbol} {tf}: {e}")
        return None

def aggregate_features(tf_features):
    """Aggregate features across timeframes into a single profile."""
    if not tf_features:
        return None
    
    df = pd.DataFrame(tf_features)
    
    # Group by symbol and aggregate
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    agg_dict = {col: 'mean' for col in numeric_cols if col != 'bar_count'}
    agg_dict['bar_count'] = 'sum'
    
    # We also want to keep track of multi-timeframe patterns
    aggregated = {}
    
    for col in numeric_cols:
        if col == 'bar_count':
            aggregated[f'{col}_total'] = df[col].sum()
        else:
            aggregated[f'{col}_mean'] = df[col].mean()
            aggregated[f'{col}_std'] = df[col].std()
    
    # Timeframe-specific features (1d is most important for character)
    for tf in TIMEFRAMES:
        tf_row = df[df['timeframe'] == tf]
        if not tf_row.empty:
            row = tf_row.iloc[0]
            aggregated[f'{tf}_atr'] = row.get('avg_atr_pct', np.nan)
            aggregated[f'{tf}_needle_freq'] = row.get('needle_freq', np.nan)
    
    return aggregated

def main():
    print("=" * 80)
    print("🧬 COIN DNA EXTRACTION")
    print(f"Coins: {len(DEFAULT_COINS)} | Timeframes: {TIMEFRAMES}")
    print("=" * 80)
    
    all_profiles = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        print(f"[{i}/{len(DEFAULT_COINS)}] {symbol}...", end=" ", flush=True)
        
        tf_features = []
        for tf in TIMEFRAMES:
            features = extract_features_for_timeframe(symbol, tf)
            if features:
                tf_features.append(features)
        
        if tf_features:
            # Aggregate across timeframes
            profile = aggregate_features(tf_features)
            if profile:
                profile['symbol'] = symbol
                all_profiles.append(profile)
                print(f"✓ ({len(tf_features)} TFs)")
        else:
            print("✗ No data")
    
    # Save results
    if all_profiles:
        df_profiles = pd.DataFrame(all_profiles)
        
        output_dir = Path("library/coin_dna")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / "profiles.parquet"
        df_profiles.to_parquet(output_path, index=False)
        
        print("\n" + "=" * 80)
        print(f"✅ Extracted DNA for {len(all_profiles)} coins")
        print(f"📁 Saved to: {output_path}")
        print(f"📊 Features per coin: {len(df_profiles.columns)}")
        print("=" * 80)
        
        # Quick stats
        print("\n📈 Quick Feature Stats:")
        numeric_cols = df_profiles.select_dtypes(include=[np.number]).columns[:5]
        print(df_profiles[numeric_cols].describe().round(2))
    else:
        print("\n❌ No profiles extracted!")

if __name__ == "__main__":
    main()
