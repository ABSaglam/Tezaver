"""
Test suite for rally_labeler module.
Verifies that rally outcome computation works correctly.
"""

import pandas as pd
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.outcomes.rally_labeler import _compute_outcomes_for_indices


def test_compute_outcomes_simple_uptrend():
    """Test rally outcome computation with a simple uptrend."""
    # Create uptrend: 10 -> 11 -> 12 -> 13 -> 14
    close = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0])
    indices = pd.Series([0, 1])  # Test first two bars
    lookahead = 3

    outcomes = _compute_outcomes_for_indices(close, indices, lookahead)

    # Check that gain is positive for uptrend
    g0 = outcomes["future_max_gain_pct"].iloc[0]
    assert g0 > 0.0, "Expected positive gain for uptrend"
    
    # For first index (price 10), looking ahead 3 bars sees price 13 (30% gain)
    assert g0 > 0.2, f"Expected significant gain, got {g0}"

    # Check rally label is valid
    lbl0 = outcomes["rally_label"].iloc[0]
    assert isinstance(lbl0, str), "Rally label should be a string"
    assert lbl0 in ["rally_5p", "rally_10p", "rally_20p", "none"], f"Invalid rally label: {lbl0}"


def test_compute_outcomes_simple_downtrend():
    """Test rally outcome computation with a downtrend."""
    # Create downtrend: 14 -> 13 -> 12 -> 11 -> 10
    close = pd.Series([14.0, 13.0, 12.0, 11.0, 10.0])
    indices = pd.Series([0])
    lookahead = 3

    outcomes = _compute_outcomes_for_indices(close, indices, lookahead)

    # Loss should be negative (or close to it)
    loss = outcomes["future_max_loss_pct"].iloc[0]
    assert loss < 0.0, "Expected negative max loss for downtrend"


def test_compute_outcomes_flat_market():
    """Test rally outcome computation with flat prices."""
    close = pd.Series([100.0] * 10)
    indices = pd.Series([0, 1, 2])
    lookahead = 5

    outcomes = _compute_outcomes_for_indices(close, indices, lookahead)

    # Flat market should have minimal gains/losses
    for i in range(len(indices)):
        gain = outcomes["future_max_gain_pct"].iloc[i]
        loss = outcomes["future_max_loss_pct"].iloc[i]
        assert abs(gain) < 0.01, f"Expected near-zero gain for flat market, got {gain}"
        assert abs(loss) < 0.01, f"Expected near-zero loss for flat market, got {loss}"
        
        # Rally label should be "none" for flat market
        lbl = outcomes["rally_label"].iloc[i]
        assert lbl == "none", f"Expected 'none' rally label for flat market, got {lbl}"
