"""
Test suite for indicator_engine module.
Verifies that build_features_for_history_df generates expected columns.
"""

import pandas as pd
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.features.indicator_engine import build_features_for_history_df


def test_indicator_engine_basic_features_exist():
    """Test that indicator engine generates all expected feature columns."""
    # Create simple test data with enough rows for indicators to calculate
    data = {
        "timestamp": list(range(100)),
        "open": [100 + i * 0.5 for i in range(100)],
        "high": [101 + i * 0.5 for i in range(100)],
        "low": [99 + i * 0.5 for i in range(100)],
        "close": [100 + i * 0.5 for i in range(100)],
        "volume": [1000 + i * 10 for i in range(100)],
    }
    df = pd.DataFrame(data)

    # Build features
    feat = build_features_for_history_df(df)

    # Verify essential columns exist
    expected_columns = [
        "rsi",
        "macd_line",
        "macd_signal",
        "atr",
        "ema_fast",
        "ema_mid",
        "ema_slow",
        "vol_rel",
    ]
    
    for col in expected_columns:
        assert col in feat.columns, f"Expected column '{col}' not found in features"

    # Verify length consistency
    assert len(feat) == len(df), "Feature DataFrame length doesn't match input length"
    
    # Verify no all-NaN columns (at least some valid values)
    for col in expected_columns:
        assert feat[col].notna().any(), f"Column '{col}' is all NaN"


def test_indicator_engine_output_types():
    """Test that indicator engine outputs are numeric."""
    data = {
        "timestamp": list(range(50)),
        "open": [100] * 50,
        "high": [105] * 50,
        "low": [95] * 50,
        "close": [100] * 50,
        "volume": [1000] * 50,
    }
    df = pd.DataFrame(data)

    feat = build_features_for_history_df(df)

    # Check that numeric columns are indeed numeric
    numeric_cols = ["rsi", "macd_line", "atr", "ema_fast", "vol_rel"]
    for col in numeric_cols:
        if col in feat.columns:
            assert pd.api.types.is_numeric_dtype(feat[col]), f"Column '{col}' is not numeric"
