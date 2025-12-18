import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.engine.policy_state_machine import PolicyStateMachine, PolicyState, PolicyPhase, PolicyDecision


class TestPolicyStateMachineV1(unittest.TestCase):
    def setUp(self):
        self.config = BulutConfig(
            mode="TEST",
            policy_min_hold_bars=2,
            policy_dust_policy="FLATTEN_AFTER",
            policy_htf_veto_enabled=True
        )
        self.ctx = MagicMock(spec=BulutContext)
        self.ctx.persistence = MagicMock()
        self.ctx.telemetry = MagicMock()
        self.ctx.config = self.config
        
        self.policy = PolicyStateMachine(self.config)

    def test_closed_bar_only_blocks_open(self):
        """Test C1: Open blocked if bar not closed."""
        decision, reason = self.policy.evaluate_open(
            self.ctx, "BTCUSDT", datetime.now(timezone.utc),
            bar_is_closed=False, 
            htf_ok=True, 
            position_open=False
        )
        self.assertEqual(decision, PolicyDecision.BLOCK_OPEN)
        self.assertEqual(reason, "BAR_NOT_CLOSED")

    def test_htf_veto_blocks_open(self):
        """Test HTF Veto logic."""
        decision, reason = self.policy.evaluate_open(
            self.ctx, "BTCUSDT", datetime.now(timezone.utc),
            bar_is_closed=True, 
            htf_ok=False, 
            position_open=False
        )
        self.assertEqual(decision, PolicyDecision.BLOCK_OPEN)
        self.assertEqual(reason, "HTF_VETO")
        
    def test_open_allowed_and_transition(self):
        """Test successful Open evaluation and transition."""
        self.ctx.persistence.get_policy_state.return_value = None # IDLE
        
        ts = datetime.now(timezone.utc)
        decision, reason = self.policy.evaluate_open(
            self.ctx, "BTCUSDT", ts,
            bar_is_closed=True, 
            htf_ok=True, 
            position_open=False
        )
        self.assertEqual(decision, PolicyDecision.ALLOW_OPEN)
        
        # Simulate Decider calling transition
        self.policy.transition_on_open_submit(self.ctx, "BTCUSDT", ts)
        
        # Verify save
        self.ctx.persistence.upsert_policy_state.assert_called()
        call_args = self.ctx.persistence.upsert_policy_state.call_args[0][0]
        self.assertEqual(call_args["phase"], PolicyPhase.OPENING.value)
        self.assertEqual(call_args["opened_cycle_ts"], ts.isoformat())

    def test_hold_next_closed_logic_deterministic(self):
        """Test deterministic bar counting for hold logic."""
        t0 = datetime.now(timezone.utc)
        state_dict = {
            "symbol": "BTCUSDT",
            "phase": "EFFECTIVE", # Already effective (simulating transition)
            "opened_cycle_ts": t0.isoformat(),
            "hold_bars_remaining": 2,
            "last_update_ms": 1000
        }
        self.ctx.persistence.get_policy_state.return_value = state_dict
        
        # Test 1: Only 1 bar passed (15m) -> Should be BLOCKED (held 1, need 2)
        # 15m = 900s
        t1 = t0 + timedelta(minutes=15)
        decision, reason = self.policy.evaluate_close(
            self.ctx, "BTCUSDT", t1, 
            bar_is_closed=True, position_open=True
        )
        self.assertEqual(decision, PolicyDecision.BLOCK_CLOSE)
        self.assertIn("MIN_HOLD_NOT_MET", reason) 
        # Verify it calculated remaining=1
        self.ctx.persistence.upsert_policy_state.assert_called()
        last_save = self.ctx.persistence.upsert_policy_state.call_args[0][0]
        self.assertEqual(last_save["hold_bars_remaining"], 1)

        # Test 2: 2 bars passed (30m) -> Should be ALLOWED
        t2 = t0 + timedelta(minutes=30)
        decision, reason = self.policy.evaluate_close(
            self.ctx, "BTCUSDT", t2, 
            bar_is_closed=True, position_open=True
        )
        self.assertEqual(decision, PolicyDecision.ALLOW_CLOSE)

    def test_save_state_includes_ooo_timestamp(self):
        """Test save_state includes timestamp for OOO protection."""
        # Use a fresh IDLE state
        self.ctx.persistence.get_policy_state.return_value = None
        ts = datetime.now(timezone.utc)
        
        self.policy.transition_on_open_submit(self.ctx, "BTCUSDT", ts)
        
        call_args = self.ctx.persistence.upsert_policy_state.call_args[0][0]
        self.assertIn("last_update_ms", call_args)
        self.assertTrue(call_args["last_update_ms"] > 0)

    def test_reconcile_resets_to_idle(self):
        """Test reconciliation resets state."""
        # Setup mock to return a non-IDLE state
        self.ctx.persistence.get_policy_state.return_value = {
            "symbol": "BTCUSDT", "phase": "OPENING", 
            "opened_cycle_ts": None, "hold_bars_remaining": 0,
            "last_update_ms": 1000
        }
        
        self.policy.reconcile_after_execution(self.ctx, "BTCUSDT", position_closed=True)
        
        save_call = self.ctx.persistence.upsert_policy_state.call_args[0][0]
        self.assertEqual(save_call["phase"], PolicyPhase.IDLE.value)

if __name__ == '__main__':
    unittest.main()
