# Tezaver Bulut - Panel Guard Contract Tests
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from unittest.mock import patch

def test_guarded_render_catches_exception():
    """Test that guarded_render catches exceptions from the failing function."""
    
    def failing_fn():
        raise RuntimeError("Oops, I crashed!")
        
    with patch("streamlit.container"), \
         patch("streamlit.error"), \
         patch("streamlit.markdown"), \
         patch("streamlit.columns", return_value=(MagicMock(), MagicMock())), \
         patch("streamlit.button"), \
         patch("streamlit.link_button"), \
         patch("streamlit.toggle"), \
         patch("streamlit.code"):
         
        try:
            guarded_render("Test Panel", failing_fn)
        except Exception as e:
            import pytest
            pytest.fail(f"guarded_render let exception escape: {e}")
            
from unittest.mock import MagicMock
