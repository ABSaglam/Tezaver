import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from datetime import datetime

# Mock aiohttp
sys.modules["aiohttp"] = MagicMock()

from tezaver.bulut.engine.scheduler import AsyncScheduler
from tezaver.bulut.core.config import BulutConfig

class TestFairSchedulerV1(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Initialize frozen config with overrides
        self.config = BulutConfig(
            universe_scan_max_per_cycle=3,
            universe_scan_priority_slots=1,
            poll_interval_seconds=0.1
        )
        # self.config.universe_scan_max_per_cycle = 3  <-- CANNOT ASSIGN
        
        self.scheduler = AsyncScheduler(self.config)
        self.scheduler._poller = AsyncMock()
        
        # Mock Context
        self.mock_ctx = MagicMock()
        self.mock_ctx.persistence = MagicMock()
        self.mock_ctx.universe_source = MagicMock()
        self.mock_ctx.universe_source.load.return_value = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        
        self.mock_ctx.telemetry = MagicMock()
        self.mock_ctx.ranking_stabilizer = MagicMock()
        self.mock_ctx.ranking_stabilizer.get_last_ranking.return_value = None
        
        self.mock_ctx.bars_store = MagicMock()
        self.mock_ctx.pattern_loader = MagicMock()
        self.mock_ctx.exit_profile_loader = MagicMock()
        self.mock_ctx.exit_engine = MagicMock()
        self.mock_ctx.decider = MagicMock()
        self.mock_ctx.decider.decide.return_value = [] # No plans
        self.mock_ctx.exit_engine.evaluate_exits.return_value = []
        self.mock_ctx.executor = AsyncMock()
        self.mock_ctx.allowlist_source = MagicMock()
        self.mock_ctx.allowlist_source.load.return_value = []
        self.mock_ctx.config = self.config
        
        # Mock Persistence State
        self.state_db = {}
        
        def get_state(key):
            return self.state_db.get(key)
            
        def set_state(key, val):
            self.state_db[key] = str(val)
            
        self.mock_ctx.persistence.get_system_state.side_effect = get_state
        self.mock_ctx.persistence.set_system_state.side_effect = set_state
        
        # Mock Poller default: Success
        self.scheduler._poller.run_cycle.return_value = (3, []) # (count, failed)

        # Mock Scanner
        patcher = patch('tezaver.bulut.engine.scanner.run_scan')
        self.mock_run_scan = patcher.start()
        self.mock_run_scan.return_value = MagicMock(cycle_ts="2024-01-01T00:00:00")
        self.addCleanup(patcher.stop)

    async def test_round_robin_no_starvation(self):
        """Verify that all 10 symbols are picked over 4 cycles (Batch=3)."""
        # Cycle 1: [A, B, C] -> Cursor 3
        await self.scheduler._run_cycle_logic(self.mock_ctx, 1000)
        self.assertEqual(int(self.state_db["sched_cursor"]), 3)
        self.scheduler._poller.run_cycle.assert_called()
        args1 = self.scheduler._poller.run_cycle.call_args[0][0]
        self.assertEqual(sorted(args1), ["A", "B", "C"])
        
        # Cycle 2: [D, E, F] -> Cursor 6
        await self.scheduler._run_cycle_logic(self.mock_ctx, 2000)
        self.assertEqual(int(self.state_db["sched_cursor"]), 6)
        args2 = self.scheduler._poller.run_cycle.call_args[0][0]
        self.assertEqual(sorted(args2), ["D", "E", "F"])
        
        # Cycle 3: [G, H, I] -> Cursor 9
        await self.scheduler._run_cycle_logic(self.mock_ctx, 3000)
        args3 = self.scheduler._poller.run_cycle.call_args[0][0]
        self.assertEqual(sorted(args3), ["G", "H", "I"])
        
        # Cycle 4: [J, A, B] -> Cursor 12%10 = 2
        await self.scheduler._run_cycle_logic(self.mock_ctx, 4000)
        args4 = self.scheduler._poller.run_cycle.call_args[0][0]
        self.assertEqual(sorted(args4), ["A", "B", "J"]) # Set sorting
        self.assertEqual(int(self.state_db["sched_cursor"]), 2)

    async def test_priority_lane_backpressure(self):
        """Verify that failed symbols are prioritized in next cycle."""
        # Cycle 1: Pick [A, B, C]. But 'B' fails.
        self.scheduler._poller.run_cycle.return_value = (2, ["B"])
        
        await self.scheduler._run_cycle_logic(self.mock_ctx, 1000)
        
        # Assert State has 'B' as missed
        self.assertEqual(self.state_db["sched_missed"], "B")
        
        # Cycle 2: Should pick 'B' (Priority) + [D, E] (RR). Cap is 1 for Prio.
        # Max cycle is 3. Prio lane uses 1 slot for 'B'. Remaining 2 slots for RR.
        # Next RR after A,B,C is D,E.
        self.scheduler._poller.run_cycle.return_value = (3, []) # Success
        
        await self.scheduler._run_cycle_logic(self.mock_ctx, 2000)
        
        args2 = self.scheduler._poller.run_cycle.call_args[0][0]
        self.assertIn("B", args2)
        self.assertIn("D", args2)
        self.assertIn("E", args2)
        
        # Verify 'B' is cleared from missed (since returned failed list is empty)
        self.assertEqual(self.state_db["sched_missed"], "")

    async def test_priority_cap_enforcement(self):
        """Verify priority cap limits how many priority items are picked."""
        object.__setattr__(self.config, 'universe_scan_priority_slots', 1)
        object.__setattr__(self.config, 'universe_scan_max_per_cycle', 3)
        
        # Inject 2 missed items: "X", "Y"
        self.state_db["sched_missed"] = "X,Y"
        self.mock_ctx.universe_source.load.return_value = ["A", "B", "C", "D"]
        
        # Expect: Pick 1 Prio ("X" or "Y") + 2 RR ("A", "B"). Total 3.
        # Since logic sorts: `0 if x in s_missed else 1`. It doesn't guarantee order between missed.
        # But usually list(set) order.
        
        await self.scheduler._run_cycle_logic(self.mock_ctx, 1000)
        
        args = self.scheduler._poller.run_cycle.call_args[0][0]
        self.assertEqual(len(args), 3)
        self.assertTrue(any(x in args for x in ["X", "Y"]))
        # At least one missed item should be there.
        # And since only 1 priority slot, only 1 missed item (or top20) should be there if possible?
        # Logic: priority_list[:prio_cap].
        
        priority_in_batch = [x for x in args if x in ["X", "Y"]]
        self.assertEqual(len(priority_in_batch), 1) 

if __name__ == '__main__':
    unittest.main()
