import pytest
from tezaver.matrix.core.bars import Bar, require_closed_bar

def test_closed_bar_valid():
    b = Bar(100, 1.0, 2.0, 0.5, 1.5, is_closed=True)
    require_closed_bar(b)

def test_open_bar_forbidden():
    b = Bar(100, 1.0, 2.0, 0.5, 1.5, is_closed=False)
    with pytest.raises(ValueError, match="Processing allowed only on closed bars"):
        require_closed_bar(b)
