# Test UI Imports
"""Verify UI modules can be imported without error."""

import unittest
import sys
from unittest.mock import MagicMock

class TestUIImports(unittest.TestCase):
    """Tests for UI module imports."""
    
    def setUp(self):
        # Mock streamlit to avoid runtime environment issues
        sys.modules["streamlit"] = MagicMock()
    
    def test_import_matrix_operator_tab(self):
        """Should import matrix_operator_tab without error."""
        try:
            import tezaver.ui.matrix_operator_tab
        except Exception as e:
            self.fail(f"Failed to import tezaver.ui.matrix_operator_tab: {e}")
            
    def test_rendering_functions_exist(self):
        """Required rendering functions should exist."""
        import tezaver.ui.matrix_operator_tab
        self.assertTrue(hasattr(tezaver.ui.matrix_operator_tab, "render_matrix_operator_tab"))

if __name__ == "__main__":
    unittest.main()
