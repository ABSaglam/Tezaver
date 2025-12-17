# Test Matrix Presets
"""Unit tests for matrix_presets module."""

import unittest
from tezaver.ui.matrix_presets import (
    get_preset,
    resolve_preset,
    preset_help_text,
    get_preset_names,
    ALL_PRESETS,
    MatrixPreset,
    PRESET_CANLI,
    PRESET_SAVAS,
    PRESET_SNIPER,
)


class TestMatrixPresets(unittest.TestCase):
    """Tests for MatrixPreset resolution."""
    
    def test_default_resolution_for_each_preset(self):
        """Each preset should resolve with correct defaults."""
        # CANLI
        canli = resolve_preset("CANLI")
        self.assertEqual(canli["name"], "CANLI")
        self.assertEqual(canli["safety_level"], "TESTNET")
        self.assertTrue(canli["is_live"])
        self.assertFalse(canli["is_backtest"])
        
        # SAVAŞ
        savas = resolve_preset("SAVAŞ")
        self.assertEqual(savas["name"], "SAVAŞ")
        self.assertEqual(savas["safety_level"], "SIM")
        self.assertTrue(savas["is_backtest"])
        self.assertFalse(savas["is_live"])
        
        # SNIPER
        sniper = resolve_preset("SNIPER")
        self.assertEqual(sniper["name"], "SNIPER")
        self.assertTrue(sniper["is_sniper"])
        self.assertEqual(sniper["timeframes"], ["15m"])
    
    def test_override_precedence(self):
        """Overrides should take precedence over preset defaults."""
        # Override safety_level
        resolved = resolve_preset("CANLI", {"safety_level": "GERÇEK"})
        self.assertEqual(resolved["safety_level"], "GERÇEK")
        
        # Override allowlist
        resolved = resolve_preset("SAVAŞ", {"allowlist": ["XRPUSDT"]})
        self.assertEqual(resolved["allowlist"], ["XRPUSDT"])
        
        # Override timeframes
        resolved = resolve_preset("SNIPER", {"timeframes": ["1h", "4h"]})
        self.assertEqual(resolved["timeframes"], ["1h", "4h"])
        
        # None values should not override
        resolved = resolve_preset("CANLI", {"safety_level": None})
        self.assertEqual(resolved["safety_level"], "TESTNET")  # Original default
    
    def test_unknown_preset_falls_back_to_canli(self):
        """Unknown preset name should fallback to CANLI."""
        resolved = resolve_preset("UNKNOWN_PRESET")
        self.assertEqual(resolved["name"], "CANLI")
    
    def test_help_texts_exist(self):
        """All required help topics should have text."""
        topics = [
            "profil", "guvenlik_seviyesi", "allowlist", "timeframe",
            "on_kontrol", "kart_kapisi", "risk_freni", "reconcile",
            "islem_tekrari", "olay_gezgini", "paketler", "cozumlenmis_ayarlar"
        ]
        for topic in topics:
            text = preset_help_text(topic)
            self.assertNotEqual(text, "Bilgi mevcut değil.", f"Missing help for: {topic}")
            self.assertGreater(len(text), 10, f"Help text too short for: {topic}")
    
    def test_preset_names_list(self):
        """get_preset_names should return all preset names."""
        names = get_preset_names()
        self.assertIn("CANLI", names)
        self.assertIn("SAVAŞ", names)
        self.assertIn("SNIPER", names)
        self.assertEqual(len(names), 3)
    
    def test_preset_to_dict(self):
        """MatrixPreset.to_dict should return serializable dict."""
        preset = get_preset("CANLI")
        d = preset.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("name", d)
        self.assertIn("safety_level", d)
        self.assertIn("allowlist", d)


if __name__ == "__main__":
    unittest.main()
