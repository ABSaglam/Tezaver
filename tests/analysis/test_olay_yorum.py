
import unittest
from tezaver.analysis.olay_yorum import calculate_ahenk_score, calculate_betrayal_risk

class TestOlayYorum(unittest.TestCase):
    def test_ahenk_deterministic(self):
        # Case 1: Ideal setup
        # Base 0.5 + 0.2 (RSI 40-70) + 0.2 (ATR > 0.5) = 0.9
        details = {"trigger_rsi": "50", "trigger_atr_pct": "1.0"}
        score, reason = calculate_ahenk_score(details)
        self.assertAlmostEqual(score, 0.9)
        self.assertIn("RSI_OK", reason)
        self.assertIn("ATR_ACTIVE", reason)
        
        # Case 2: Overbought
        # Base 0.5 - 0.1 (RSI > 70) = 0.4
        details = {"trigger_rsi": "80", "trigger_atr_pct": "0.1"}
        score, reason = calculate_ahenk_score(details)
        self.assertAlmostEqual(score, 0.4)
        self.assertIn("RSI_HOT", reason)
        
    def test_betrayal_deterministic(self):
        # Case 1: Profit (No betrayal)
        # Min -1%, Max +10%. Risk = 1/10 = 0.1
        details = {"future_min_pct": "-0.01", "future_max_gain_pct": "0.1"}
        score, reason = calculate_betrayal_risk(details)
        self.assertAlmostEqual(score, 0.1)
        self.assertEqual(reason, "STABLE")
        # Logic: 0.1 < 0.2 -> STABLE? Wait
        # if score > 0.8: BETRAYED
        # elif score > 0.5: SHAKY
        # elif score > 0.2: NORMAL_PULLBACK
        # else: STABLE. (0.1 is STABLE)
        
        # Correction: 0.1 is < 0.2 so reason is default "STABLE".
        
        # Let's fix test checking reason logic
        # 0.1 is "STABLE"
        # 0.3 is "NORMAL_PULLBACK"
        
        # Case 2: Betrayal
        # Min -5%, Max +2%. Risk = 5/2 = 2.5 (clipped to 1.0)
        details = {"future_min_pct": "-0.05", "future_max_gain_pct": "0.02"}
        score, reason = calculate_betrayal_risk(details)
        self.assertEqual(score, 1.0)
        self.assertEqual(reason, "BETRAYED")
        
    def test_ui_integration_simulation(self):
        """Simulate trade_replay_data logic slightly."""
        # Just ensure functions don't crash on missing keys
        score, _ = calculate_ahenk_score({})
        self.assertEqual(score, 0.5) # Base
        
        score, _ = calculate_betrayal_risk({})
        # future_max_gain=0 -> NO_GAIN
        self.assertEqual(score, 0.0)

if __name__ == '__main__':
    unittest.main()
