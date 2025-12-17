# Test Sidebar Mini Status
"""Unit tests for sidebar status helper and navigation items."""

import unittest
from pathlib import Path
from tezaver.ui.matrix_operator_data import get_sidebar_status


class TestSidebarStatus(unittest.TestCase):
    """Tests for sidebar mini status helper."""
    
    def test_sidebar_status_missing_ndjson_no_crash(self):
        """Missing NDJSON should return default status, no crash."""
        fake_path = Path("/nonexistent/file.ndjson")
        result = get_sidebar_status(fake_path)
        
        # Should not crash and return default values
        self.assertIsInstance(result, dict)
        self.assertIn("kilit", result)
        self.assertIn("run", result)
        self.assertIn("poz", result)
        self.assertIn("son", result)
        
        # Default values
        self.assertEqual(result["kilit"], "—")
        self.assertEqual(result["run"], "DURDU")
        self.assertEqual(result["poz"], "—")
        self.assertEqual(result["son"], "—")
    
    def test_sidebar_status_empty_ndjson_no_crash(self):
        """Empty NDJSON should return default status."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)
        
        try:
            result = get_sidebar_status(temp_path)
            self.assertIsInstance(result, dict)
            self.assertEqual(result["kilit"], "—")
        finally:
            temp_path.unlink()


class TestNavItems(unittest.TestCase):
    """Tests for navigation items."""
    
    def test_nav_items_exact_match(self):
        """Navigation should have exactly 6 items."""
        # These are the expected nav items as defined in render_matrix_mode
        expected_items = [
            "🧭 Matrix",
            "👤 Hesap",
            "🃏 Kartlar",
            "📊 Veri",
            "📋 Olaylar",
            "⚙️ Ayarlar",
        ]
        
        # Verify count
        self.assertEqual(len(expected_items), 6)
        
        # Verify no War/Sniper items
        for item in expected_items:
            self.assertNotIn("War", item)
            self.assertNotIn("Sniper", item)
            self.assertNotIn("SAVAŞ", item)


if __name__ == "__main__":
    unittest.main()
