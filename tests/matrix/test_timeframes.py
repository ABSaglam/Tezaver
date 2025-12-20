import pytest
from tezaver.matrix.core.timeframes import parse_timeframe_to_seconds

def test_parse_standard_tf():
    assert parse_timeframe_to_seconds("15m") == 900
    assert parse_timeframe_to_seconds("1h") == 3600
    assert parse_timeframe_to_seconds("4h") == 14400

def test_parse_invalid_tf():
    with pytest.raises(ValueError):
        parse_timeframe_to_seconds("1m")
