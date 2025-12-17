
import tests.mock_env
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from tezaver.matrix.live.live_policy import HoldNextClosedPolicy, PolicyState, CellPolicyState

class TestSchedulerVeto(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.policy = HoldNextClosedPolicy(gateway=self.gateway)
        
    def test_ltf_veto_logic(self):
        """Verify LTF open is vetoed if HTF decision is VETO."""
        symbol = "BTCUSDT"
        tf = "15m"
        pid = "p1"
        ts = "2025-01-01T10:00:00+00:00"
        
        # Scenario 1: OPEN signal + VETO context -> RESULT: WAIT (Action filtered)
        # Actually, Veto doesn't return BLOCK, it just doesn't OPEN.
        # But wait, logic in `handle_tick`:
        # if tf == "15m" and htf_decision == "VETO": emit event, return WAIT/SKIP?
        
        # Let's check implementation
        # The implementation I saw prints "HTF_VETO_APPLIED" and emits event.
        # It then does NOT call `_handle_open`. It returns... wait, I need to check what it returns.
        # It likely returns PolicyResult(action="VETOED"...) or just returns early.
        
        # If I mock the emit, I can check if it was emitted.
        self.policy._emit_event = MagicMock()
        
        res = self.policy.handle_tick(
            symbol, tf, pid, ts, 
            decision="OPEN", 
            htf_decision="VETO"
        )
        
        # Expect veto
        self.policy._emit_event.assert_called()
        
        # Verify Veto Event
        emitted_types = [c[0][0]["event_type"] for c in self.policy._emit_event.call_args_list]
        self.assertIn("HTF_VETO_APPLIED", emitted_types)
        
        self.assertEqual(res.action, "VETOED") 
        self.assertTrue(res.success) # Based on code reading, success=True returned

    def test_ltf_allow_logic(self):
        """Verify LTF open proceeds if HTF decision is ALLOW or None."""
        symbol = "BTCUSDT"
        tf = "15m"
        pid = "p1"
        ts = "2025-01-01T10:15:00+00:00"
        
        # Scenario 2: OPEN signal + ALLOW context -> proceed to OPEN
        self.policy._emit_event = MagicMock()
        self.policy._handle_open = MagicMock(return_value="OPEN_CALLED")
        
        res = self.policy.handle_tick(
            symbol, tf, pid, ts, 
            decision="OPEN", 
            htf_decision="ALLOW"
        )
        
        self.policy._handle_open.assert_called()
        
        # Scenario 3: OPEN signal + No Context (None) -> proceed to OPEN (Default Allow)
        self.policy._handle_open.reset_mock()
        res = self.policy.handle_tick(
             symbol, tf, pid, ts, 
             decision="OPEN", 
             htf_decision=None
        )
        self.policy._handle_open.assert_called()

    def test_htf_permission_emission(self):
        """Verify HTF bar emits permission event."""
        symbol = "BTCUSDT"
        tf = "4h"
        pid = "p1"
        ts = "2025-01-01T12:00:00+00:00"
        
        self.policy._emit_event = MagicMock()
        
        # Strategy says OPEN -> Permission ALLOW
        self.policy.handle_tick(symbol, tf, pid, ts, decision="OPEN")
        
        found = False
        for call in self.policy._emit_event.call_args_list:
            evt = call[0][0]
            if evt["event_type"] == "HTF_PERMISSION_EVAL":
                found = True
                self.assertEqual(evt["decision"], "ALLOW")
                break
        self.assertTrue(found, "HTF_PERMISSION_EVAL not emitted")
        
        # Strategy says None (hold/flat) -> Permission VETO (Simple logic for now)
        self.policy._emit_event.reset_mock()
        self.policy.handle_tick(symbol, tf, pid, ts, decision=None)
        
        found = False
        for call in self.policy._emit_event.call_args_list:
            evt = call[0][0]
            if evt["event_type"] == "HTF_PERMISSION_EVAL":
                found = True
                self.assertEqual(evt["decision"], "VETO")
                break
        self.assertTrue(found, "HTF_PERMISSION_EVAL not emitted on None decision")


from tezaver.matrix.live.live_loop_service import LiveLoopService

class TestLiveLoopServiceStaleness(unittest.TestCase):
    def setUp(self):
        # Reset singleton logic if possible, or just instantiate directly if allowed
        # LiveLoopService uses __new__ singleton pattern.
        # We can access the singleton and reset relevant state.
        self.service = LiveLoopService.get()
        self.service._htf_permissions = {} 

    def test_fresh_context(self):
        """Fresh permission is returned."""
        symbol = "ETHUSDT"
        now = datetime.now(timezone.utc)
        self.service._htf_permissions[symbol] = {
            "decision": "VETO",
            "tf": "4h",
            "ts": now - timedelta(minutes=10) # 10m old (Fresh)
        }
        
        ctx = self.service._provide_context(symbol, "15m")
        self.assertEqual(ctx.get("htf_decision"), "VETO")
        
    def test_stale_context(self):
        """Stale permission is ignored (None)."""
        symbol = "ETHUSDT"
        now = datetime.now(timezone.utc)
        # 4h TTL is 260m. Make it 300m old.
        self.service._htf_permissions[symbol] = {
            "decision": "VETO",
            "tf": "4h",
            "ts": now - timedelta(minutes=300)
        }
        
        ctx = self.service._provide_context(symbol, "15m")
        self.assertIsNone(ctx.get("htf_decision"))

    def test_legacy_format(self):
        """Legacy string format is accepted (no staleness check)."""
        symbol = "SOLUSDT"
        self.service._htf_permissions[symbol] = "ALLOW"
        ctx = self.service._provide_context(symbol, "15m")
        self.assertEqual(ctx.get("htf_decision"), "ALLOW")

if __name__ == '__main__':
    unittest.main()
