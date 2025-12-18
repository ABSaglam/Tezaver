# Test Determinism Bridge v1

import unittest
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock aiohttp before imports
sys.modules["aiohttp"] = MagicMock()

import unittest
from datetime import datetime, timezone, timedelta
import asyncio

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.engine.policy_state_machine import PolicyStateMachine, PolicyPhase, PolicyState
from tezaver.bulut.services.state_reducer import StateReducer
# Delayed import of Executor inside tests or after mock
# from tezaver.bulut.engine.executor import Executor

class TestDeterminismBridgeV1(unittest.TestCase):
    def setUp(self):
        self.config = BulutConfig()
        self.ctx = MagicMock(spec=BulutContext)
        self.ctx.config = self.config
        
        # Mocks
        self.ctx.persistence = MagicMock()
        self.ctx.telemetry = MagicMock()
        
        # Services
        self.policy = PolicyStateMachine(self.config)
        self.reducer = StateReducer(self.config, self.ctx.persistence, self.ctx.telemetry)
        
        # Import Executor here
        from tezaver.bulut.engine.executor import Executor
        self.ExecutorClass = Executor
        
        # Executor needs async setup often, usually we strict mock it or its dependencies
        self.ctx.state_reducer = self.reducer
        
    def test_same_inputs_same_policy_decision_id(self):
        """Verify deterministic decision ID generation."""
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sym = "BTCUSDT"
        
        did1 = self.policy.make_decision_id(sym, ts, "OPEN_CHECK", "IDLE")
        did2 = self.policy.make_decision_id(sym, ts, "OPEN_CHECK", "IDLE")
        
        self.assertEqual(did1, did2)
        self.assertTrue(len(did1) > 0)
        
        # Different inputs -> diff ID
        did3 = self.policy.make_decision_id(sym, ts + timedelta(minutes=1), "OPEN_CHECK", "IDLE")
        self.assertNotEqual(did1, did3)

    def test_plan_exec_transition_deduped_by_reducer(self):
        """Verify reducer prevents duplicate transition application."""
        plan_id = "test_plan_001"
        did = "did_123"
        to_state = "EXECUTED"
        ts = 1000
        
        # Configure mock sequence: First True (Success), Second False (Duplicate)
        self.ctx.persistence.try_mark_event_applied.side_effect = [True, False]
        
        # First call (Success)
        res1 = self.reducer.apply_plan_transition(plan_id, to_state, did, ts)
        self.assertTrue(res1)
        
        # Second call (Duplicate)
        res2 = self.reducer.apply_plan_transition(plan_id, to_state, did, ts)
        self.assertFalse(res2)
        
        # Verify persistence finalize called only once
        self.ctx.persistence.finalize_plan_execution.assert_called_once()

    def test_start_recovery_resolves_and_finalizes_once(self):
        """Test Executor recovery logic (Mocked)."""
        # Create executor instance with mocks
        exec_inst = self.ExecutorClass(self.config)
        exec_inst._client = AsyncMock() # Mock Binance client
        exec_inst._resolve_ambiguous_order = AsyncMock() 
        exec_inst._resolve_ambiguous_order.return_value = {"status": "FILLED", "orderId": 123}
        
        # Mock persistence returning one EXECUTING plan
        self.ctx.persistence.get_plans_by_status.return_value = [{
            "symbol": "BTCUSDT", "idempotency_key": "plan_orphan"
        }]
        
        # Reducer mock
        self.ctx.state_reducer = MagicMock()
        
        # Run
        asyncio.run(exec_inst.recover_executing_plans(self.ctx))
        
        # Verify resolve called
        exec_inst._resolve_ambiguous_order.assert_awaited()
        
        # Verify reducer applied transition
        self.ctx.state_reducer.apply_plan_transition.assert_called_once()
        args = self.ctx.state_reducer.apply_plan_transition.call_args[0]
        # args: plan_id, to_state, decision_id, ts, result
        self.assertEqual(args[0], "plan_orphan")
        self.assertEqual(args[1], "EXECUTED") # Because we mocked FILLED
        self.assertEqual(args[2], "RECOVERY")

    def test_policy_repair_when_position_open_but_state_idle(self):
        """Test policy drift repair."""
        # Setup: Open position exists
        self.ctx.persistence.get_open_positions.return_value = [{
            "symbol": "BTCUSDT", "entry_ts": datetime.now(timezone.utc).isoformat()
        }]
        
        # Setup: State is IDLE (drift)
        # Policy.get_state mocks
        # We need to mock get_policy_state on persistence
        self.ctx.persistence.get_policy_state.return_value = {
            "symbol": "BTCUSDT", "phase": "IDLE"
        }
        
        self.policy.repair_state_drift(self.ctx)
        
        # Verify upsert called with EFFECTIVE
        self.ctx.persistence.upsert_policy_state.assert_called()
        saved = self.ctx.persistence.upsert_policy_state.call_args[0][0]
        self.assertEqual(saved["phase"], "EFFECTIVE")
        self.assertEqual(saved["last_reason"], "REPAIR_DRIFT")

if __name__ == '__main__':
    unittest.main()
