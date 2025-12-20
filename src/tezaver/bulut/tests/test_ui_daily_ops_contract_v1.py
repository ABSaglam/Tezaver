"""
Tezaver Bulut - Daily Ops Contract Tests
"""
import pytest
from unittest.mock import MagicMock, patch
from tezaver.bulut.ui.contracts.page_registry import Registry
from tezaver.bulut.ui.register_pages import register_all_pages

def test_daily_ops_registered():
    """Verify registry presence."""
    Registry.reset()
    register_all_pages()
    page = Registry.get_page("daily_ops")
    assert page.id == "daily_ops"

@patch("tezaver.bulut.ui.pages.daily_ops.backend_status")
@patch("tezaver.bulut.ui.pages.daily_ops.call_api")
@patch("tezaver.bulut.ui.pages.daily_ops.st")
def test_render_contract(mock_st, mock_call, mock_backend):
    """Verify render_page handles execution safely."""
    from tezaver.bulut.ui.pages.daily_ops import render_page
    
    # Mock Backend OK
    mock_backend.return_value = (True, "OK", None)
    
    # Mock API Calls
    mock_call.return_value.ok = True
    
    # Mock Columns unpacking
    def columns_side_effect(spec, *args, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [MagicMock() for _ in range(count)]
    mock_st.columns.side_effect = columns_side_effect
    
    render_page(MagicMock())
    
    mock_st.title.assert_called()
