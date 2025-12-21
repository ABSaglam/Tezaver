import pytest
from tezaver.matrix.core.lookahead_guard import LookaheadProtectedList, LookaheadViolation

def test_lookahead_protected_list_basic():
    data = [10, 20, 30, 40, 50]
    protected = LookaheadProtectedList(data, initial_index=0)
    
    # Can access index 0
    assert protected[0] == 10
    
    # Cannot access index 1
    with pytest.raises(LookaheadViolation):
        _ = protected[1]
    
    # Advance index
    protected.set_current_index(1)
    assert protected[1] == 20
    
    # Cannot access index 2
    with pytest.raises(LookaheadViolation):
        _ = protected[2]

def test_lookahead_protected_list_slice():
    data = list(range(100))
    protected = LookaheadProtectedList(data, initial_index=10)
    
    # Slice [0:11] is OK (last index is 10)
    res = protected[0:11]
    assert len(res) == 11
    assert res[-1] == 10
    
    # Slice [0:12] should fail (exposes index 11)
    with pytest.raises(LookaheadViolation):
        _ = protected[0:12]

def test_lookahead_protected_list_len():
    data = [1, 2, 3, 4, 5]
    protected = LookaheadProtectedList(data, initial_index=2)
    
    # Length should be 3 (indices 0, 1, 2)
    assert len(protected) == 3
    
    # Advance
    protected.set_current_index(4)
    assert len(protected) == 5

def test_lookahead_protected_list_iter():
    data = [1, 2, 3, 4, 5]
    protected = LookaheadProtectedList(data, initial_index=1)
    
    items = list(protected)
    assert items == [1, 2]
