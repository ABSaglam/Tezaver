import pytest
from tezaver.matrix.core.data_quality import validate_bar_sequence

def test_empty_sequence():
    report = validate_bar_sequence([])
    assert not report.ok
    assert "Sequence is empty" in report.issues

def test_clean_sequence():
    report = validate_bar_sequence([100, 200, 300])
    assert report.ok
    assert not report.issues

def test_duplicates():
    report = validate_bar_sequence([100, 200, 200, 300])
    assert not report.ok
    assert "Duplicate timestamp found: 200" in report.issues

def test_out_of_order():
    report = validate_bar_sequence([100, 150, 120])
    assert not report.ok
    assert "Out-of-order timestamp: 120 after 150" in report.issues
