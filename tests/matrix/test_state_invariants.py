import pytest
from tezaver.matrix.core.state import RunState, validate_state

def test_valid_state():
    s = RunState()
    assert not validate_state(s)

def test_invalid_qty():
    s = RunState()
    s.position.qty = -1
    errs = validate_state(s)
    assert any("Negative position" in e for e in errs)

def test_invalid_price():
    s = RunState()
    s.position.entry_price = -100
    errs = validate_state(s)
    assert any("Negative entry price" in e for e in errs)
