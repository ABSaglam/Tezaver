#!/usr/bin/env python3
"""
ASM v6 - Phase 1: Adaptive Config Generator

Generates coin-specific adaptive thresholds from rally soul analysis
Uses IQR (Interquartile Range) for flexible thresholds
"""

import json
import numpy as np
from pathlib import Path

def generate_adaptive_config(rally_soul_path, output_path):
    """
    Generate adaptive config from rally soul analysis
    
    Args:
        rally_soul_path: Path to rally soul JSON
        output_path: Where to save adaptive config
    """
    
    # Load rally soul
    with open(rally_soul_path, 'r') as f:
        soul = json.load(f)
    
    patterns = soul['patterns']
    
    # Extract all values
    rsi_values = []
    vol_values = []
    atr_values = []
    
    for p in patterns:
        cond = p['committed_conditions']
        if cond.get('rsi') is not None:
            rsi_values.append(cond['rsi'])
        if cond.get('vol_ratio') is not None:
            vol_values.append(cond['vol_ratio'])
        if cond.get('atr_ratio') is not None:
            atr_values.append(cond['atr_ratio'])
    
    # Calculate statistics
    def calc_stats(values):
        if not values:
            return None
        
        return {
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'mean': float(np.mean(values)),
            'median': float(np.median(values)),
            'q25': float(np.percentile(values, 25)),
            'q75': float(np.percentile(values, 75)),
            'iqr_low': float(np.percentile(values, 25)),
            'iqr_high': float(np.percentile(values, 75)),
            'count': len(values)
        }
    
    rsi_stats = calc_stats(rsi_values)
    vol_stats = calc_stats(vol_values)
    atr_stats = calc_stats(atr_values)
    
    # Build adaptive config
    config = {
        'coin': 'ALGOUSDT',  # Can be parameterized later
        'version': 'v6',
        'adaptive_config': {
            'ema_alignment_required': True,  # 100% in ALGO rallies
            'rsi': {
                **rsi_stats,
                # Adaptive thresholds: IQR ± tolerance
                'threshold_strict': [rsi_stats['q25'], rsi_stats['q75']],  # IQR only
                'threshold_relaxed': [max(rsi_stats['min'], rsi_stats['q25'] - 5),  # IQR - 5
                                      min(rsi_stats['max'], rsi_stats['q75'] + 5)]   # IQR + 5
            },
            'vol_ratio': {
                **vol_stats,
                # Volume: median * factor
                'threshold_strict': vol_stats['median'],
                'threshold_relaxed': vol_stats['median'] * 0.8  # 80% of median
            },
            'atr_ratio': {
                **atr_stats,
                'threshold_min': atr_stats['median'] * 0.8,
                'threshold_max': atr_stats['median'] * 1.5
            }
        },
        'thresholds_explanation': {
            'strict': 'Uses IQR (Q25-Q75) for RSI, median for volume. High precision, low recall.',
            'relaxed': 'Uses IQR ± 5 for RSI, 80% median for volume. Better recall, may reduce precision.'
        },
        'recommended_mode': 'relaxed'  # Based on v5 results (too strict)
    }
    
    # Save config
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config

def print_config_summary(config):
    """Print readable summary of config"""
    print("="*80)
    print("🔧 ADAPTIVE CONFIG GENERATED")
    print("="*80)
    
    print(f"\nCoin: {config['coin']}")
    print(f"Version: {config['version']}")
    
    rsi = config['adaptive_config']['rsi']
    vol = config['adaptive_config']['vol_ratio']
    
    print("\n📊 RSI Thresholds:")
    print(f"  Strict (IQR):     [{rsi['threshold_strict'][0]:.1f}, {rsi['threshold_strict'][1]:.1f}]")
    print(f"  Relaxed (IQR±5):  [{rsi['threshold_relaxed'][0]:.1f}, {rsi['threshold_relaxed'][1]:.1f}]")
    print(f"  Historical Range: [{rsi['min']:.1f}, {rsi['max']:.1f}]")
    print(f"  Median: {rsi['median']:.1f}")
    
    print("\n📊 Volume Ratio Thresholds:")
    print(f"  Strict (Median):     >{vol['threshold_strict']:.2f}")
    print(f"  Relaxed (0.8×Median): >{vol['threshold_relaxed']:.2f}")
    print(f"  Historical Range: [{vol['min']:.2f}, {vol['max']:.2f}]")
    print(f"  Median: {vol['median']:.2f}")
    
    print(f"\n💡 Recommended Mode: {config['recommended_mode'].upper()}")
    print(f"   Rationale: {config['thresholds_explanation'][config['recommended_mode']]}")

if __name__ == "__main__":
    rally_soul_path = "/Users/alisaglam/TezaverMac/data/algo_rally_soul.json"
    output_path = "/Users/alisaglam/TezaverMac/data/algo_adaptive_config_v6.json"
    
    print("🚀 Generating Adaptive Config for ASM v6...")
    
    config = generate_adaptive_config(rally_soul_path, output_path)
    print_config_summary(config)
    
    print(f"\n📁 Config saved to: {output_path}")
    print("\n✅ Phase 1 Complete!")
