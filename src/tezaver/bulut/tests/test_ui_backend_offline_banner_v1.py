# Tezaver Bulut - Backend Offline Banner Contract Tests
from tezaver.bulut.ui.contracts.backend_guard import render_backend_offline_banner, backend_status
from unittest.mock import patch, MagicMock

def test_backend_status_offline():
    """Test backend_status handles connection failure safely."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        
        ok, info, error = backend_status("http://localhost:9999")
        assert not ok
        assert "Connection refused" in error

def test_render_banner_no_throw():
    """Test that render_backend_offline_banner does not throw exceptions."""
    # We can't easily assert Streamlit output in unit test without a framework,
    # but we can ensure it doesn't crash the interpreter (smoke test).
    
    # Mock streamlit functions to avoid "No SessionContext" errors if run outside streamlit
    with patch("streamlit.warning"), \
         patch("streamlit.expander"), \
         patch("streamlit.markdown"), \
         patch("streamlit.info"), \
         patch("streamlit.code"), \
         patch("streamlit.button"), \
         patch("streamlit.rerun"):
         
         try:
            render_backend_offline_banner("http://localhost:8000", "Some error")
         except Exception as e:
             import pytest
             pytest.fail(f"render_backend_offline_banner raised exception: {e}")
