from tezaver.matrix.core.story_signatures import check_signatures

def test_signatures_empty():
    assert check_signatures({}) == []

def test_signatures_valid():
    sigs = {
        "rsi": {"min": 30.0, "max": 70.0, "mean": 50.0},
        "macd": {"min": -1.0, "max": 1.0, "mean": 0.0}
    }
    assert check_signatures(sigs) == []

def test_signatures_invalid_key():
    sigs = {"invalid_metric": {"min":0, "max":1, "mean":0.5}}
    errors = check_signatures(sigs)
    assert any("Unknown signature key" in e for e in errors)

def test_signatures_logic_error():
    sigs = {
        "rsi": {"min": 80, "max": 20, "mean": 50} # Min > Max
    }
    errors = check_signatures(sigs)
    assert any("min (80) > max (20)" in e for e in errors)

def test_signatures_rsi_bounds():
    sigs = {
        "rsi": {"min": -10, "max": 50, "mean": 20}
    }
    errors = check_signatures(sigs)
    assert any("out of bounds" in e for e in errors)
