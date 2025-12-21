import pytest
from tezaver.matrix.data.data_integrity import validate_candles

def test_validate_candles_clean():
    candles = [
        {"timestamp": 1000},
        {"timestamp": 2000},
        {"timestamp": 3000}
    ]
    res = validate_candles(candles, 1000)
    assert res["ok"] is True
    assert res["reasons"] == []

def test_validate_candles_out_of_order():
    candles = [
        {"timestamp": 1000},
        {"timestamp": 3000},
        {"timestamp": 2000}
    ]
    res = validate_candles(candles, 1000)
    assert res["ok"] is False
    assert "OUT_OF_ORDER" in res["reasons"]
    assert res["out_of_order_count"] == 1

def test_validate_candles_duplicates():
    candles = [
        {"timestamp": 1000},
        {"timestamp": 2000},
        {"timestamp": 2000},
        {"timestamp": 3000}
    ]
    res = validate_candles(candles, 1000)
    assert res["ok"] is False
    assert "DUPLICATE_TS" in res["reasons"]
    assert res["duplicate_count"] == 1

def test_validate_candles_gaps():
    candles = [
        {"timestamp": 1000},
        {"timestamp": 2000},
        {"timestamp": 4000} # Gap of 1000ms (1 bar)
    ]
    res = validate_candles(candles, 1000)
    assert res["ok"] is False
    assert "GAP_DETECTED" in res["reasons"]
    assert res["gap_count"] == 1
    assert res["max_gap_bars"] == 1

def test_validate_candles_multiple_issues():
    candles = [
        {"timestamp": 2000},
        {"timestamp": 1000}, # Out of order
        {"timestamp": 1000}, # Duplicate
        {"timestamp": 4000}  # Gap
    ]
    res = validate_candles(candles, 1000)
    assert res["ok"] is False
    assert len(res["reasons"]) == 3
