from tezaver.matrix.core.multi_tf import compute_higher_tf_closes, validate_multi_tf_alignment

def test_compute_higher_tf():
    # 15m bars: 0, 900, 1800, 2700, 3600 (1h)
    # Convert to MS
    base = [t*1000 for t in [0, 900, 1800, 2700, 3600, 4500]]
    higher_tf_sec = 3600
    
    higher = compute_higher_tf_closes(base, higher_tf_sec)
    expected = [t*1000 for t in [0, 3600]]
    assert higher == expected

def test_validate_alignment_ok():
    base = [t*1000 for t in [0, 3600, 7200]]
    higher = [t*1000 for t in [0, 3600]]
    errs = validate_multi_tf_alignment(base, higher, 3600)
    assert not errs

def test_validate_alignment_fail_orphan():
    base = [0, 900000] # 0, 900s
    higher = [3600000] # 3600s not in base
    errs = validate_multi_tf_alignment(base, higher, 3600)
    assert any("orphan" in e for e in errs)

def test_validate_alignment_fail_boundary():
    base = [0, 100000, 200000]
    higher = [100000] # in base, but 100s is not 3600s aligned
    errs = validate_multi_tf_alignment(base, higher, 3600)
    assert any("not aligned" in e for e in errs)
