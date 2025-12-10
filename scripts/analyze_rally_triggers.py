"""
Rally Trigger Analyzer
======================

Analyzes what triggers rally starts by examining pre-rally conditions
and identifying successful patterns.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

# Add src to path
import sys
project_root = Path.cwd()
if str(project_root / 'src') not in sys.path:
    sys.path.insert(0, str(project_root / 'src'))

from tezaver.core import coin_cell_paths
from tezaver.snapshots.snapshot_engine import load_features


def load_rally_data(symbol: str, timeframe: str = '15m') -> Optional[pd.DataFrame]:
    """Load rally events for a symbol and timeframe."""
    if timeframe == '15m':
        path = coin_cell_paths.get_fast15_rallies_path(symbol)
    else:
        path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
    
    if not path.exists():
        print(f"❌ Rally data not found: {path}")
        return None
    
    try:
        df = pd.read_parquet(path)
        print(f"✅ Loaded {len(df)} rallies from {path.name}")
        return df
    except Exception as e:
        print(f"❌ Error loading rallies: {e}")
        return None


def analyze_precursors(
    rally_df: pd.DataFrame,
    features_df: pd.DataFrame,
    lookback: int = 5
) -> pd.DataFrame:
    """
    Analyze pre-rally conditions for each rally event.
    
    Args:
        rally_df: Rally events with event_time
        features_df: Price/indicator features with timestamp index
        lookback: Number of bars to look back before rally
    
    Returns:
        DataFrame with rally events + precursor analysis
    """
    # Ensure features_df has datetime index
    if 'timestamp' in features_df.columns:
        features_df = features_df.set_index('timestamp')
    
    if not isinstance(features_df.index, pd.DatetimeIndex):
        features_df.index = pd.to_datetime(features_df.index)
    
    results = []
    
    for idx, rally in rally_df.iterrows():
        event_time = pd.to_datetime(rally['event_time'])
        
        # Get the bar index in features_df
        try:
            event_idx = features_df.index.get_indexer([event_time], method='nearest')[0]
        except:
            continue
        
        if event_idx < lookback:
            continue  # Not enough history
        
        # Get pre-rally window
        pre_rally = features_df.iloc[event_idx - lookback:event_idx]
        event_bar = features_df.iloc[event_idx]
        
        if len(pre_rally) < lookback:
            continue
        
        # === PRECURSOR ANALYSIS ===
        
        # 1. RSI Trend
        rsi_values = pre_rally['rsi'].values if 'rsi' in pre_rally.columns else []
        if len(rsi_values) >= 3:
            rsi_trend = 'rising' if rsi_values[-1] > rsi_values[0] else 'falling'
            rsi_slope = (rsi_values[-1] - rsi_values[0]) / len(rsi_values)
        else:
            rsi_trend = 'unknown'
            rsi_slope = 0
        
        # 2. Volume Trend
        vol_values = pre_rally['vol_rel'].values if 'vol_rel' in pre_rally.columns else []
        if len(vol_values) >= 3:
            vol_trend = 'increasing' if vol_values[-1] > vol_values[0] else 'decreasing'
            vol_spike = vol_values[-1] > 1.5  # Last bar had high volume
        else:
            vol_trend = 'unknown'
            vol_spike = False
        
        # 3. MACD State
        macd_hist = pre_rally['macd_hist'].values if 'macd_hist' in pre_rally.columns else []
        if len(macd_hist) >= 2:
            # Check for bullish crossover (negative to positive)
            macd_cross = macd_hist[-2] < 0 and macd_hist[-1] > 0
            macd_state = 'bullish_cross' if macd_cross else ('positive' if macd_hist[-1] > 0 else 'negative')
        else:
            macd_cross = False
            macd_state = 'unknown'
        
        # 4. RSI Oversold Recovery
        rsi_current = event_bar.get('rsi', np.nan)
        rsi_prev = rsi_values[-1] if len(rsi_values) > 0 else np.nan
        rsi_oversold_recovery = (
            not pd.isna(rsi_prev) and 
            not pd.isna(rsi_current) and
            rsi_prev < 30 and 
            rsi_current > 35
        )
        
        # 5. Price Consolidation
        high_values = pre_rally['high'].values if 'high' in pre_rally.columns else []
        low_values = pre_rally['low'].values if 'low' in pre_rally.columns else []
        if len(high_values) >= 3 and len(low_values) >= 3:
            price_range = (max(high_values) - min(low_values)) / min(low_values)
            is_consolidation = price_range < 0.03  # Less than 3% range
        else:
            is_consolidation = False
        
        # Compile precursor data
        precursor = {
            'event_time': event_time,
            'rally_gain': rally.get('future_max_gain_pct', 0),
            'rally_shape': rally.get('rally_shape', 'unknown'),
            'quality_score': rally.get('quality_score', 0),
            
            # Precursors
            'rsi_trend': rsi_trend,
            'rsi_slope': rsi_slope,
            'vol_trend': vol_trend,
            'vol_spike': vol_spike,
            'macd_state': macd_state,
            'macd_cross': macd_cross,
            'rsi_oversold_recovery': rsi_oversold_recovery,
            'is_consolidation': is_consolidation,
            
            # Current state
            'rsi_current': rsi_current,
            'vol_rel_current': event_bar.get('vol_rel', np.nan),
            'macd_hist_current': event_bar.get('macd_hist', np.nan),
        }
        
        results.append(precursor)
    
    return pd.DataFrame(results)


def identify_triggers(precursor_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify trigger patterns for each rally.
    
    Returns:
        DataFrame with trigger classifications
    """
    triggers = []
    
    for idx, row in precursor_df.iterrows():
        trigger_list = []
        trigger_score = 0
        
        # Pattern 1: MACD Bullish Cross
        if row['macd_cross']:
            trigger_list.append('MACD_CROSS')
            trigger_score += 0.8
        
        # Pattern 2: Volume Breakout
        if row['vol_spike']:
            trigger_list.append('VOLUME_SPIKE')
            trigger_score += 0.9
        
        # Pattern 3: RSI Oversold Recovery
        if row['rsi_oversold_recovery']:
            trigger_list.append('RSI_OVERSOLD_RECOVERY')
            trigger_score += 0.7
        
        # Pattern 4: Consolidation Breakout
        if row['is_consolidation'] and row['vol_spike']:
            trigger_list.append('CONSOLIDATION_BREAKOUT')
            trigger_score += 0.85
        
        # Pattern 5: Rising RSI + Volume
        if row['rsi_trend'] == 'rising' and row['vol_trend'] == 'increasing':
            trigger_list.append('RSI_VOL_CONVERGENCE')
            trigger_score += 0.75
        
        # Determine primary trigger
        if len(trigger_list) == 0:
            primary = 'NO_CLEAR_TRIGGER'
        else:
            primary = trigger_list[0]
        
        triggers.append({
            'event_time': row['event_time'],
            'primary_trigger': primary,
            'all_triggers': ','.join(trigger_list),
            'trigger_count': len(trigger_list),
            'trigger_score': trigger_score,
            'rally_gain': row['rally_gain'],
            'quality_score': row['quality_score']
        })
    
    return pd.DataFrame(triggers)


def calculate_trigger_success(trigger_df: pd.DataFrame) -> Dict:
    """
    Calculate success rates for each trigger pattern.
    
    Returns:
        Dictionary with trigger statistics
    """
    stats = {}
    
    # Group by primary trigger
    for trigger_name in trigger_df['primary_trigger'].unique():
        subset = trigger_df[trigger_df['primary_trigger'] == trigger_name]
        
        if len(subset) == 0:
            continue
        
        # Calculate metrics
        total_count = len(subset)
        avg_gain = subset['rally_gain'].mean()
        median_gain = subset['rally_gain'].median()
        
        # Success rates (>= thresholds)
        success_5p = (subset['rally_gain'] >= 0.05).sum() / total_count
        success_10p = (subset['rally_gain'] >= 0.10).sum() / total_count
        success_20p = (subset['rally_gain'] >= 0.20).sum() / total_count
        
        # Quality score
        avg_quality = subset['quality_score'].mean()
        
        stats[trigger_name] = {
            'total_samples': total_count,
            'avg_gain_pct': float(avg_gain * 100),
            'median_gain_pct': float(median_gain * 100),
            'success_rate_5p': float(success_5p),
            'success_rate_10p': float(success_10p),
            'success_rate_20p': float(success_20p),
            'avg_quality_score': float(avg_quality)
        }
    
    # Sort by success rate
    sorted_stats = dict(sorted(
        stats.items(), 
        key=lambda x: x[1]['success_rate_10p'], 
        reverse=True
    ))
    
    return sorted_stats


def analyze_trigger_combinations(trigger_df: pd.DataFrame) -> Dict:
    """
    Analyze multi-trigger combinations for better predictions.
    
    Returns:
        Dictionary with combination statistics
    """
    combo_stats = {}
    
    for idx, row in trigger_df.iterrows():
        triggers = row['all_triggers'].split(',') if row['all_triggers'] else []
        
        if len(triggers) < 2:
            continue  # Skip single triggers
        
        # Sort to ensure consistent combo naming
        combo_name = ' + '.join(sorted(triggers))
        
        if combo_name not in combo_stats:
            combo_stats[combo_name] = {
                'rallies': [],
                'gains': [],
                'quality_scores': []
            }
        
        combo_stats[combo_name]['rallies'].append(row['event_time'])
        combo_stats[combo_name]['gains'].append(row['rally_gain'])
        combo_stats[combo_name]['quality_scores'].append(row['quality_score'])
    
    # Calculate statistics for each combination
    results = {}
    for combo, data in combo_stats.items():
        if len(data['gains']) < 3:  # Need at least 3 samples
            continue
        
        gains = data['gains']
        qualities = data['quality_scores']
        
        results[combo] = {
            'total_samples': len(gains),
            'avg_gain_pct': float(np.mean(gains) * 100),
            'median_gain_pct': float(np.median(gains) * 100),
            'success_rate_5p': float(sum(1 for g in gains if g >= 0.05) / len(gains)),
            'success_rate_10p': float(sum(1 for g in gains if g >= 0.10) / len(gains)),
            'success_rate_20p': float(sum(1 for g in gains if g >= 0.20) / len(gains)),
            'avg_quality_score': float(np.mean(qualities))
        }
    
    # Sort by success rate 10p
    sorted_results = dict(sorted(
        results.items(),
        key=lambda x: x[1]['success_rate_10p'],
        reverse=True
    ))
    
    return sorted_results


def analyze_pattern_sequences(precursor_df: pd.DataFrame) -> Dict:
    """
    Analyze what happens in the 5 bars before rally starts.
    
    Returns:
        Pattern frequency analysis
    """
    patterns = {
        'rsi_rising_then_spike': 0,
        'volume_gradual_increase': 0,
        'macd_building_momentum': 0,
        'consolidation_then_breakout': 0,
        'rsi_oversold_bounce': 0
    }
    
    for idx, row in precursor_df.iterrows():
        # Pattern 1: RSI Rising + Volume Spike
        if row['rsi_trend'] == 'rising' and row['vol_spike']:
            patterns['rsi_rising_then_spike'] += 1
        
        # Pattern 2: Volume Gradual Increase
        if row['vol_trend'] == 'increasing':
            patterns['volume_gradual_increase'] += 1
        
        # Pattern 3: MACD Cross Soon After
        if row['macd_cross']:
            patterns['macd_building_momentum'] += 1
        
        # Pattern 4: Consolidation Breakout
        if row['is_consolidation'] and row['vol_spike']:
            patterns['consolidation_then_breakout'] += 1
        
        # Pattern 5: RSI Oversold Bounce
        if row['rsi_oversold_recovery']:
            patterns['rsi_oversold_bounce'] += 1
    
    total = len(precursor_df)
    pattern_freq = {
        pattern: {
            'count': count,
            'frequency_pct': float(count / total * 100) if total > 0 else 0
        }
        for pattern, count in patterns.items()
    }
    
    return pattern_freq


def main():
    """Main analysis function."""
    print("=" * 60)
    print("🔬 RALLY TRIGGER ANALYSIS")
    print("=" * 60)
    
    symbol = "BTCUSDT"
    timeframe = "15m"
    
    # 1. Load rally data
    print(f"\n📊 Loading rally data for {symbol} ({timeframe})...")
    rally_df = load_rally_data(symbol, timeframe)
    
    if rally_df is None or rally_df.empty:
        print("❌ No rally data available. Exiting.")
        return
    
    # 2. Load features
    print(f"\n📈 Loading features for {symbol} ({timeframe})...")
    try:
        features_df = load_features(symbol, timeframe)
        print(f"✅ Loaded {len(features_df)} bars of features")
    except Exception as e:
        print(f"❌ Error loading features: {e}")
        return
    
    # 3. Analyze precursors
    print(f"\n🔍 Analyzing pre-rally conditions (5 bars lookback)...")
    precursor_df = analyze_precursors(rally_df, features_df, lookback=5)
    print(f"✅ Analyzed {len(precursor_df)} rallies")
    
    # 4. Identify triggers
    print(f"\n⚡ Identifying trigger patterns...")
    trigger_df = identify_triggers(precursor_df)
    print(f"✅ Classified {len(trigger_df)} triggers")
    
    # 5. Calculate success rates
    print(f"\n📊 Calculating trigger success rates...")
    success_stats = calculate_trigger_success(trigger_df)
    
    # 6. Analyze trigger combinations
    print(f"\n🔗 Analyzing multi-trigger combinations...")
    combo_stats = analyze_trigger_combinations(trigger_df)
    
    # 7. Analyze pattern sequences
    print(f"\n📈 Analyzing pre-rally pattern sequences...")
    pattern_freq = analyze_pattern_sequences(precursor_df)
    
    # 8. Print results
    print("\n" + "=" * 60)
    print("🎯 TRIGGER SUCCESS ANALYSIS")
    print("=" * 60)
    
    for idx, (trigger, stats) in enumerate(success_stats.items(), 1):
        print(f"\n{idx}. {trigger}")
        print(f"   Samples: {stats['total_samples']}")
        print(f"   Avg Gain: {stats['avg_gain_pct']:.2f}%")
        print(f"   Success Rate >=5%: {stats['success_rate_5p']:.1%}")
        print(f"   Success Rate >=10%: {stats['success_rate_10p']:.1%}")
        print(f"   Success Rate >=20%: {stats['success_rate_20p']:.1%}")
        print(f"   Avg Quality: {stats['avg_quality_score']:.1f}/100")
    
    # 7. Save results
    output_dir = Path("analysis_output")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"rally_trigger_analysis_{symbol}_{timeframe}.json"
    
    full_results = {
        'symbol': symbol,
        'timeframe': timeframe,
        'total_rallies_analyzed': len(trigger_df),
        'single_triggers': success_stats,
        'trigger_combinations': combo_stats,
        'pattern_frequencies': pattern_freq
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(full_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
