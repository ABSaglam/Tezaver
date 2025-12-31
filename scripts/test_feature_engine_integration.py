"""
Feature Engine Integration Test
================================
"Cerrah Protokolü: Gerçek Veri ile Doğrulama"

This script tests the feature engine with real rally data.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tezaver.core.rally_store import RallyStore
from tezaver.smyrna.data_access import get_rally_context, validate_no_future_data
from tezaver.smyrna.feature_engine import extract_all_features
import pandas as pd

def test_feature_extraction():
    """
    Test feature extraction on real rally data.
    """
    print("=" * 70)
    print("FEATURE ENGINE INTEGRATION TEST")
    print("=" * 70)
    
    # 1. Load a real rally with data file
    store = RallyStore()
    rallies = store.list_rallies(limit=50)
    
    if not rallies:
        print("❌ No rallies found in database!")
        return False
    
    # Find a rally with existing data file
    rally = None
    for r in rallies:
        from tezaver.core import coin_cell_paths
        cell_path = coin_cell_paths.get_coin_cell_dir(r['symbol'])
        tf_file = cell_path / f"{r['timeframe']}.parquet"
        if tf_file.exists():
            rally = r
            break
    
    if not rally:
        print(f"❌ No rallies found with existing price data!")
        print(f"   Checked {len(rallies)} rallies")
        return False
    
    rally_id = rally['id']
    
    print(f"\n📋 Test Rally: {rally_id}")
    print(f"   Symbol: {rally['symbol']}")
    print(f"   Timeframe: {rally['timeframe']}")
    print(f"   Event Time: {rally['event_time']}")
    
    # 2. Get rally context (with temporal leakage protection)
    print(f"\n🔍 Loading rally context (T-60 → T-0)...")
    try:
        context = get_rally_context(rally_id, lookback_bars=60, strict_mode=True)
        print(f"✅ Context loaded: {len(context)} bars")
        print(f"   Time range: {context.index.min()} → {context.index.max()}")
        
        # Validate temporal safety
        is_safe = validate_no_future_data(rally_id, context)
        if not is_safe:
            print("❌ TEMPORAL LEAKAGE DETECTED!")
            return False
        print("✅ Temporal safety verified")
        
    except Exception as e:
        print(f"❌ Failed to load context: {e}")
        return False
    
    # 3. Extract features
    print(f"\n🧬 Extracting features...")
    try:
        features = extract_all_features(context)
        print(f"✅ Feature extraction complete")
        print(f"   Original columns: {len(context.columns)}")
        print(f"   Total columns: {len(features.columns)}")
        print(f"   New features: {len(features.columns) - len(context.columns)}")
        
    except Exception as e:
        print(f"❌ Feature extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. Validate features
    print(f"\n🔬 Validating features...")
    
    # Check for NaN
    nan_cols = features.columns[features.isna().any()].tolist()
    if nan_cols:
        print(f"⚠️  NaN values in {len(nan_cols)} columns:")
        for col in nan_cols[:5]:  # Show first 5
            nan_count = features[col].isna().sum()
            print(f"     - {col}: {nan_count} NaNs")
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
    
    # Check boundary conditions
    print(f"\n📊 Boundary Check:")
    
    # RSI (0-100)
    if 'rsi_14' in features.columns:
        rsi_min, rsi_max = features['rsi_14'].min(), features['rsi_14'].max()
        print(f"   RSI: [{rsi_min:.2f}, {rsi_max:.2f}]", end="")
        if 0 <= rsi_min and rsi_max <= 100:
            print(" ✅")
        else:
            print(" ❌ OUT OF RANGE!")
            return False
    
    # Stochastic (0-100)
    if 'stoch_k' in features.columns:
        stoch_min, stoch_max = features['stoch_k'].min(), features['stoch_k'].max()
        print(f"   Stochastic K: [{stoch_min:.2f}, {stoch_max:.2f}]", end="")
        if 0 <= stoch_min and stoch_max <= 100:
            print(" ✅")
        else:
            print(" ❌ OUT OF RANGE!")
            return False
    
    # ADX (0-100)
    if 'adx_14' in features.columns:
        adx_min, adx_max = features['adx_14'].min(), features['adx_14'].max()
        print(f"   ADX: [{adx_min:.2f}, {adx_max:.2f}]", end="")
        if 0 <= adx_min and adx_max <= 100:
            print(" ✅")
        else:
            print(" ❌ OUT OF RANGE!")
            return False
    
    # 5. Display sample
    print(f"\n📋 Sample features (last 3 bars):")
    sample_cols = ['close', 'rsi_14', 'volume_ratio_20', 'macd', 'adx_14', 'ema_9']
    available_cols = [c for c in sample_cols if c in features.columns]
    print(features[available_cols].tail(3).to_string())
    
    # 6. Summary
    print(f"\n" + "=" * 70)
    print("TEST RESULT: ✅ PASSED")
    print("=" * 70)
    print(f"All features validated successfully!")
    print(f"Ready for algorithm development.")
    
    return True


if __name__ == "__main__":
    success = test_feature_extraction()
    sys.exit(0 if success else 1)
