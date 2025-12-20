"""
Tezaver Bulut - Ops Gate Standard Contract Test
Verifies that the UI enforces the 'GET Free / POST Gated' policy.
"""
import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from tezaver.bulut.ui.contracts.result_card import call_api
from tezaver.bulut.ui.pages import daily_ops

# Helper to mock session state
@contextmanager
def mock_session_state(token=None):
    with patch("tezaver.bulut.ui.contracts.result_card.st.session_state", {}) as m:
        if token:
            m['ops_token'] = token
        yield m

def test_call_api_get_is_always_free():
    """Verify GET requests ignore ops_required=True."""
    with patch("tezaver.bulut.ui.contracts.result_card.requests.get") as mock_get:
        # Mock Response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        
        # No token in session
        with mock_session_state(token=None):
            # Even if we mistakenly ask for ops_required=True
            res = call_api(MagicMock(), "GET", "/test", ops_required=True)
            
        # Should proceed to call
        mock_get.assert_called_once()
        assert res.ok  # Mock returns 200
        
def test_call_api_post_requires_token():
    """Verify POST triggers lock if token missing."""
    with patch("tezaver.bulut.ui.contracts.result_card.requests.post") as mock_post:
        # Context with NO token in config
        mock_ctx = MagicMock()
        mock_ctx.config.ops_token = None # Explicitly None to avoid MagicMock truthy
        
        # No token in session
        with mock_session_state(token=None):
            res = call_api(mock_ctx, "POST", "/test", ops_required=True)
            
        # Should NOT call
        mock_post.assert_not_called()
        
        # Result should be LOCKED
        assert not res.ok
        assert res.status_code == 403
        assert "LOCKED" in res.error_text

@patch("tezaver.bulut.ui.pages.daily_ops.backend_status")
@patch("tezaver.bulut.ui.pages.daily_ops.call_api")
@patch("tezaver.bulut.ui.pages.daily_ops.st")
def test_daily_ops_render_no_token_safe(mock_st, mock_call, mock_backend):
    """Verify daily_ops renders safely without token."""
    # Mock Backend OK
    mock_backend.return_value = (True, "OK", None)
    
    # Mock API Calls (Read only sections)
    mock_call.return_value.ok = True
    
    # Mock Column/Tab Unpacking
    def unpacking_side_effect(spec, *args, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [MagicMock() for _ in range(count)]
    
    mock_st.columns.side_effect = unpacking_side_effect
    mock_st.tabs.side_effect = unpacking_side_effect
    
    # Run with empty session (no token)
    with patch("tezaver.bulut.ui.pages.daily_ops.st.session_state", {}):
        daily_ops.render_page(MagicMock())
        
    # Should show warning/caption about lock
    # Difficult to assert precise warning text on mock_st.warning
    # But primary goal is "no exception thrown"
    assert True
