
import unittest
import sys
from unittest.mock import MagicMock

# Create necessary mocks for import test
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.sidebar"] = MagicMock()
sys.modules["streamlit.columns"] = MagicMock()
sys.modules["streamlit.tabs"] = MagicMock()
sys.modules["streamlit.expander"] = MagicMock()
sys.modules["plotly"] = MagicMock()
sys.modules["plotly.graph_objects"] = MagicMock()
sys.modules["plotly.subplots"] = MagicMock()
sys.modules["dotenv"] = MagicMock()


class TestUIImportsNoSniperWarRefs(unittest.TestCase):
    def test_import_matrix_operator_tab(self):
        """Test that matrix_operator_tab imports cleanly and has expected structure."""
        try:
            import tezaver.ui.matrix_operator_tab as mod
            # Assert render_matrix_operator_tab exists
            self.assertTrue(hasattr(mod, 'render_matrix_operator_tab'), "render_matrix_operator_tab missing")
            self.assertTrue(hasattr(mod, '_render_live_monitor_section'), "_render_live_monitor_section missing (Regression Fix)")
            
            # Assert removed functions are GONE
            self.assertFalse(hasattr(mod, '_render_sniper_arena_v4'), "Sniper Arena V4 code still present!")
            self.assertFalse(hasattr(mod, '_render_wargame_section_v2'), "War Game code still present!")
            self.assertFalse(hasattr(mod, '_render_sniper_arena_section_v2'), "Sniper Arena V2 code still present!")
            
        except ImportError as e:
            self.fail(f"Failed to import tezaver.ui.matrix_operator_tab: {e}")
    
    def test_deleted_modules_not_importable(self):
        """Ensure deleted modules are truly not importable."""
        with self.assertRaises(ImportError):
            import tezaver.ui.sniper_lab_tab
            
        with self.assertRaises(ImportError):
            import tezaver.ui.sim_lab_tab

    def test_main_panel_imports(self):
        """Test main_panel imports cleanly (no broken refs)."""
        try:
             import tezaver.ui.main_panel as mp
        except ImportError as e:
            self.fail(f"Failed to import tezaver.ui.main_panel: {e}")

if __name__ == '__main__':
    unittest.main()
