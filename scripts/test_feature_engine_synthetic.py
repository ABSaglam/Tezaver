"""
Feature Engine Synthetic Test
==============================
"Cerrah Protokolü: Mock Veri ile Validasyon"

Tests feature engine with synthetic OHLCV data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tezaver.smyrna.feature_engine import extract_all_features
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_synthetic_ohlcv(bars: int = 100) -> pd.DataFrame:
    """Create realistic synthetic OHLCV data."""
    np.random.seed(42)
    
    # Generate timestamps
    start_time = datetime(2025, 1, 1)
    timestamps = [start_time + timedelta(minutes=15*i) for i in range(bars)]
    
    # Generate realistic price movement
    base_price = 100.0
    prices = [base_price]
    
    for i in range(1, bars):
        change = np.random.normal(0, 0.02) * prices[-1]  # 2% volatility
        prices.append(prices[-1] + change)
    
    prices = np.array(prices)
    
    # Generate OHLCV
    high = prices * (1 + np.abs(np.random.normal(0, 0.01, bars)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.01, bars)))
    close = prices
    open_ = np.roll(close, 1)
    open_[0] = base_price
    
    volume = np.random.uniform(1000, 10000, bars)
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    df = df.set_index('timestamp')
    
    return df

def test_feature_extraction_synthetic():
    """Test feature extraction with synthetic data."""
    print("=" * 70)
    print("FEATURE ENGINE SYNTHETIC TEST")
    print("=" * 70)
    
    # 1. Create synthetic data
    print("\n📊 Creating synthetic OHLCV data...")
    df = create_synthetic_ohlcv(bars=200)
    print(f"✅ Created {len(df)} bars")
    print(f"   Time range: {df.index.min()} → {df.index.max()}")
    print(f"   Price range: {df['close'].min():.2f} → {df['close'].max():.2f}")
    
    # 2. Extract features
    print(f"\n🧬 Extracting features...")
    try:
        features = extract_all_features(df)
        print(f"✅ Feature extraction complete")
        print(f"   Original columns: {len(df.columns)}")
        print(f"   Total columns: {len(features.columns)}")
        new_features = len(features.columns) - len(df.columns)
        print(f"   New features: {new_features}")
        
    except Exception as e:
        print(f"❌ Feature extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. Validate features
    print(f"\n🔬 Validating features...")
    
    # Check for NaN
    nan_cols = features.columns[features.isna().any()].tolist()
    if nan_cols:
        print(f"⚠️  NaN values in {len(nan_cols)} columns")
        # NaN is expected in first few rows due to indicators
        for col in nan_cols[:5]:
            nan_count = features[col].isna().sum()
            nan_pct = (nan_count / len(features)) * 100
            print(f"     - {col}: {nan_count} NaNs ({nan_pct:.1f}%)")
            if nan_pct > 50:
                print(f"       ❌ Too many NaNs!")
                return False
    else:
        print("✅ No NaN values")
    
    # Check for infinite values
    inf_cols = []
    for col in features.columns:
        if features[col].dtype in ['float64', 'float32']:
            if (features[col] == float('inf')).any() or (features[col] == float('-inf')).any():
                inf_cols.append(col)
    
    if inf_cols:
        print(f"❌ Infinite values in {len(inf_cols)} columns: {inf_cols}")
        return False
    else:
        print("✅ No infinite values")
    
    # 4. Boundary checks
    print(f"\n📊 Boundary Check:")
    
    checks = [
        ('rsi_14', 0, 100, 'RSI'),
        ('stoch_k', 0, 100, 'Stochastic K'),
        ('stoch_d', 0, 100, 'Stochastic D'),
        ('adx_14', 0, 100, 'ADX'),
    ]
    
    for col, min_val, max_val, name in checks:
        if col in features.columns:
            actual_min = features[col].dropna().min()
            actual_max = features[col].dropna().max()
            print(f"   {name}: [{actual_min:.2f}, {actual_max:.2f}]", end="")
            if min_val <= actual_min and actual_max <= max_val:
                print(" ✅")
            else:
                print(f" ❌ OUT OF RANGE! (Expected: [{min_val}, {max_val}])")
                return False
    
    # 5. Display sample
    print(f"\n📋 Feature List (Total: {new_features}):")
    feature_names = [c for c in features.columns if c not in df.columns]
    for i, fname in enumerate(feature_names, 1):
        print(f"   {i:2d}. {fname}")
    
    print(f"\n📋 Sample Values (last 3 bars):")
    sample_cols = ['close', 'rsi_14', 'volume_ratio_20', 'macd', 'adx_14', 'ema_9', 'trend_direction']
    available_cols = [c for c in sample_cols if c in features.columns]
    print(features[available_cols].tail(3).to_string())
    
    # 6. Summary
    print(f"\n" + "=" * 70)
    print("TEST RESULT: ✅ PASSED")
    print("=" * 70)
    print(f"Feature Engine validated successfully!")
    print(f"- {new_features} features extracted")
    print(f"- All boundary checks passed")
    print(f"- No infinite values")
    print(f"- Ready for algorithm development")
    
    return True


if __name__ == "__main__":
    success = test_feature_extraction_synthetic()
    sys.exit(0 if success else 1)
