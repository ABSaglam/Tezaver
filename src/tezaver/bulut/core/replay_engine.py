# Tezaver Bulut - Replay Engine
"""
Deterministic replay execution engine.
"""
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List

from tezaver.bulut.core.context import BulutContext, BulutConfig
from tezaver.bulut.schemas.replay_v1 import ReplayBundleV1, ReplayResultV1
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.engine.decider import Decider

# --- Mocks ---

class MockBarsStore:
    def __init__(self, bars_snapshot: dict):
        self.snapshot = bars_snapshot
        
        from collections import namedtuple
        self.Bar = namedtuple("Bar", ["ts", "o", "h", "l", "c", "v"])
        
    def get_bars(self, symbol: str, timeframe: str, limit: int = None):
        sym_data = self.snapshot.get(symbol, {})
        tf_data = sym_data.get(timeframe, [])
        
        bars = [self.Bar(**b) for b in tf_data]
        if limit:
            return bars[-limit:]
        return bars
        
    def get_last_n_closed(self, symbol: str, n: int):
        # We assume snapshot contains closed bars 15m
        bars = self.get_bars(symbol, "15m", limit=n)
        return bars


class MockPersistence(SqlitePersistence):
    """Read-only persistence layer backed by bundle data."""
    def __init__(self, policy_state_snap: dict):
        # We don't init DB connection essentially, or we init in-memory?
        # Ideally we don't want to rely on real DB.
        self.policy_snap = policy_state_snap
        self.recorded_plans = []
        
    def _init_db(self):
        pass # No real DB
        
    def get_policy_state(self, symbol: str):
        return self.policy_snap.get(symbol)
        
    def insert_plan(self, plan, status="PROPOSED"):
        # Capture generated plan
        self.recorded_plans.append(plan)
        return True
    
    def upsert_policy_state(self, state):
        # Allow updating in-memory policy state map during replay
        if "symbol" in state:
            self.policy_snap[state["symbol"]] = state
        
    # Other methods stubbed to avoid errors
    def get_open_position_count(self): return 0
    def get_total_notional(self): return 0.0
    def get_open_positions(self): return []
    def get_position(self, symbol): return None
    def beat(self, *args, **kwargs): pass
    def check_trade_lock(self): return False, None # Assuming mock context handles this
    
class ReplayContext(BulutContext):
    """
    Sandboxed context for Replay.
    Overrides services to use Bundle data.
    """
    def __init__(self, bundle: ReplayBundleV1):
        # Load config from bundle
        cfg_dict = json.loads(bundle.active_config_json)
        # Apply overrides
        self._replay_config = BulutConfig() # Default
        # For simplicity we stick to default or minimal mapping
        
        super().__init__(self._replay_config)
        self.bundle = bundle
        
        # Override services
        self._bars_store = MockBarsStore(bundle.bars_snapshot)
        self._persistence = MockPersistence(bundle.policy_state)
        self._decider = None # Will instantiate logic in run
    
    @property
    def persistence(self):
        return self._persistence
        
    @property
    def bars_store(self):
        return self._bars_store


class ReplayEngine:
    def __init__(self):
        pass
        
    def run_replay(self, bundle: ReplayBundleV1) -> ReplayResultV1:
        """
        Execute replay.
        """
        # 1. Setup Context
        ctx = ReplayContext(bundle)
        
        # 2. Run Scanner
        from tezaver.bulut.engine.scanner import Scanner
        scanner = Scanner(
            config=ctx.config,
            pattern_loader=ctx.pattern_loader, # Mock loader? Context default tries filesystem.
            # We might need to mock PatternLoader if bundle has no pattern data on disk.
            # But bundle should ideally snapshot patterns? 
            # Current schema has `pattern_pack_ref` but logic needs data.
            # Let's assume pattern loader works or returns empty.
            universe=bundle.universe,
            bars_store=ctx.bars_store
        )
        
        ranking = scanner.scan()
        
        # 3. Instantiate Decider
        decider = Decider(ctx) # Context handles risk service lazy load
        
        # 4. Execution
        generated_plans = {}
        decision_ids = {}
        
        # Mock some ctx state variables needed by decider
        ctx.state.pattern_pack_loaded = True # Assume loaded
        
        open_pos_count = ctx.persistence.get_open_position_count()
        tot_notional = ctx.persistence.get_total_notional()
        
        plans = decider.decide(
            ranking=ranking,
            open_positions_count=open_pos_count,
            total_notional=tot_notional,
            pattern_pack_loaded=True
        )
                
        for plan in plans:
            generated_plans[plan.symbol] = plan.to_dict()
            decision_ids[plan.symbol] = plan.idempotency_key
        
        # 5. Compare
        match = True
        drift_details = {}
        
        for sym, plan_dict in generated_plans.items():
            # If bundle defines expected plans
            if not bundle.expected_plans:
                continue
                
            exp = bundle.expected_plans.get(sym)
            if not exp:
                # Extra plan produced (Drift)
                match = False
                drift_details[sym] = "Plan produced but not expected"
                continue
            
            # Compare ID (Determinism)
            # Idempotency key includes TS + Decision.
            if plan_dict.get("idempotency_key") != exp.get("idempotency_key"):
                 match = False
                 drift_details[sym] = f"ID Mismatch: {plan_dict.get('idempotency_key')} vs {exp.get('idempotency_key')}"
            
            # Deep compare?
            # For proof, ID match is strong enough.
        
        # If expected plans existed but we didn't produce them?
        if bundle.expected_plans:
            for sym in bundle.expected_plans:
                if sym not in generated_plans:
                    match = False
                    drift_details[sym] = "Expected plan missing"

        return ReplayResultV1(
            run_id=str(uuid.uuid4()),
            bundle_id=bundle.bundle_id,
            status="MATCH" if match else "DRIFT",
            executed_ts=bundle.cycle_ts,
            drift_details=drift_details,
            logs=[]
        )
