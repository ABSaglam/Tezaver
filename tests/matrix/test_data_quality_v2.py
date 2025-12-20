from tezaver.matrix.core.data_quality import validate_bars
from tezaver.matrix.core.bars import Bar

def mb(ts):
    return Bar(ts, 1, 1, 1, 1, True)

def test_validate_clean():
    bars = [mb(0), mb(1000), mb(2000)]
    rep = validate_bars(bars, 1) # 1 sec tf
    assert rep.ok
    assert rep.stats["count"] == 3

def test_validate_duplicates():
    bars = [mb(0), mb(1000), mb(1000), mb(2000)]
    rep = validate_bars(bars, 1)
    assert not rep.ok
    assert rep.stats["duplicates"] == 1

def test_validate_out_of_order():
    bars = [mb(0), mb(2000), mb(1000)]
    rep = validate_bars(bars, 1)
    assert not rep.ok
    assert rep.stats["out_of_order"] == 1

def test_validate_missing():
    bars = [mb(0), mb(3000)] # Gap of 3000ms (3s). TF=1s. Missing 2 bars (1000, 2000).
    rep = validate_bars(bars, 1)
    assert rep.stats["missing"] == 2

def test_validate_misaligned():
    bars = [mb(0), mb(1001)] # 1001 is misaligned to 1000ms boundary
    rep = validate_bars(bars, 1)
    assert not rep.ok
    assert rep.stats["misaligned"] == 1

def test_validate_irregular():
    # step < tf
    bars = [mb(0), mb(500)]
    rep = validate_bars(bars, 1)
    assert not rep.ok
    assert rep.stats["irregular"] == 1
