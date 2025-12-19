# Tezaver Bulut - Application Context
"""
Global application context for Tezaver Bulut.
Manages shared state and service instances.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

from tezaver.bulut.core.config import BulutConfig, get_config


@dataclass
class BulutState:
    """Runtime state for Bulut."""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_scan_ts: Optional[datetime] = None
    pattern_pack_loaded: bool = False
    pattern_pack_id: Optional[str] = None
    pattern_pack_hash: Optional[str] = None
    trade_locked: bool = True
    trade_lock_reason: Optional[str] = "PATTERN_PACK_MISSING"
    open_positions_count: int = 0
    total_notional_usdt: float = 0.0
    startup_degraded: bool = False # v0.20
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "started_at": self.started_at.isoformat(),
            "last_scan_ts": self.last_scan_ts.isoformat() if self.last_scan_ts else None,
            "pattern_pack_loaded": self.pattern_pack_loaded,
            "pattern_pack_id": self.pattern_pack_id,
            "pattern_pack_hash": self.pattern_pack_hash,
            "trade_locked": self.trade_locked,
            "trade_lock_reason": self.trade_lock_reason,
            "open_positions_count": self.open_positions_count,
            "total_notional_usdt": self.total_notional_usdt,
        }


class BulutContext:
    """
    Application context for Tezaver Bulut.
    
    Manages:
    - Configuration
    - Runtime state
    - Service references (lazy-loaded)
    """
    
    def __init__(self, config: Optional[BulutConfig] = None):
        self._config = config or get_config()
        self._state = BulutState()
        
        # Lazy-loaded services
        self._persistence = None
        self._telemetry = None
        self._pattern_loader = None
        self._universe_source = None
        self._bars_store = None
        self._exchange_cache = None
        self._governor = None
        self._group_caps = None
        self._risk = None
        self._decider = None
        self._time_sync = None
        self._status_service = None
        self._incident_bundle = None
        self._fill_sync = None
        
        # V0.12 Risk Bootstrap
        from tezaver.bulut.services.risk_rules_bootstrap import RiskRulesBootstrap
        RiskRulesBootstrap(self.config, self.telemetry).ensure_risk_rules()

    
    @property
    def config(self) -> BulutConfig:
        return self._config
    
    @property
    def state(self) -> BulutState:
        return self._state
    
    @property
    def persistence(self) -> Any:
        """Get persistence service (lazy-loaded)."""
        if self._persistence is None:
            from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
            self._persistence = SqlitePersistence(self._config.sqlite_path)
        return self._persistence
    
    @property
    def telemetry(self) -> Any:
        """Get telemetry service (lazy-loaded)."""
        if self._telemetry is None:
            from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry
            self._telemetry = NdjsonTelemetry(self._config.ndjson_path)
        return self._telemetry
    
    @property
    def pattern_loader(self) -> Any:
        """Get pattern pack loader (lazy-loaded)."""
        if self._pattern_loader is None:
            from tezaver.bulut.services.pattern_pack_loader import PatternPackLoader
            from pathlib import Path
            # Pointer path (Bulut Intel Contract v1)
            # Assumes data/bulut_intel/active_pointer.json relative to CWD
            ptr_path = Path("data/bulut_intel/active_pointer.json")
            self._pattern_loader = PatternPackLoader(self._config.pattern_pack_dir, active_pointer_path=ptr_path)
        return self._pattern_loader

    @property
    def entry_sizing_loader(self) -> Any:
        """Get entry sizing loader (lazy-loaded)."""
        if getattr(self, "_entry_sizing_loader", None) is None:
            from tezaver.bulut.services.entry_sizing_loader import EntrySizingLoader
            from pathlib import Path
            # Rule path (Bulut Entry Sizing Formulas v1)
            # data/bulut_rules/entry_sizing_profiles/
            rules_path = Path("data/bulut_rules")
            self._entry_sizing_loader = EntrySizingLoader(rules_path)
        return self._entry_sizing_loader

    @property
    def entry_sizing_resolver(self) -> Any:
        """Get entry sizing resolver (lazy-loaded)."""
        if getattr(self, "_entry_sizing_resolver", None) is None:
            from tezaver.bulut.services.entry_sizing_resolver import EntrySizingResolver
            self._entry_sizing_resolver = EntrySizingResolver(self, self.entry_sizing_loader)
        return self._entry_sizing_resolver
    
    @property
    def intel_registry(self) -> Any:
        """Get intel registry service (lazy-loaded)."""
        if getattr(self, "_intel_registry", None) is None:
            from tezaver.bulut.services.intel_registry import IntelRegistryService
            from pathlib import Path
            # Root for registry is 'data' (it creates 'bulut_intel' inside)
            self._intel_registry = IntelRegistryService(Path("data"))
        return self._intel_registry

    @property
    def universe_source(self) -> Any:
        """Get universe source (lazy-loaded)."""
        if self._universe_source is None:
            from tezaver.bulut.services.universe_source import UniverseSource
            self._universe_source = UniverseSource(self._config)
        return self._universe_source

    @property
    def ranking_stabilizer(self) -> Any:
        """Get ranking stabilizer (lazy-loaded)."""
        if getattr(self, "_ranking_stabilizer", None) is None:
            from tezaver.bulut.services.ranking_stabilizer import RankingStabilizer
            self._ranking_stabilizer = RankingStabilizer()
        return self._ranking_stabilizer
    
    @property
    def bars_store(self) -> Any:
        """Get bars store (lazy-loaded)."""
        if self._bars_store is None:
            from tezaver.bulut.services.bars_15m_store import Bars15mStore
            self._bars_store = Bars15mStore()
        return self._bars_store

    @property
    def scheduler(self) -> Any:
        """Get async scheduler (lazy-loaded)."""
        if getattr(self, "_scheduler", None) is None:
            from tezaver.bulut.engine.scheduler import AsyncScheduler
            self._scheduler = AsyncScheduler(self._config)
        return self._scheduler
    @property
    def allowlist_source(self) -> Any:
        """Get allowlist source (lazy-loaded)."""
        if getattr(self, "_allowlist_source", None) is None:
            from tezaver.bulut.services.allowlist_source import AllowlistSource
            self._allowlist_source = AllowlistSource(self._config)
        return self._allowlist_source

    @property
    def decider(self) -> Any:
        """Get decider engine (lazy-loaded)."""
        if getattr(self, "_decider", None) is None:
            from tezaver.bulut.engine.decider import Decider
            self._decider = Decider(self._config)
        return self._decider

    @property
    def executor(self) -> Any:
        """Get execution engine (lazy-loaded)."""
        if getattr(self, "_executor", None) is None:
            # P4: Dry Run Mode Switching
            if self._config.dry_run_enabled:
                from tezaver.bulut.core.executor_sim import SimulatedExecutor
                self._executor = SimulatedExecutor(self.config, self.persistence, self.telemetry)
                print("[CONTEXT] Loaded SIMULATED EXECUTOR (Dry Run Enabled)")
            else:
                from tezaver.bulut.engine.executor import Executor
                self._executor = Executor(self.config, governor=self.rate_limit_governor, time_sync=self.time_sync)
        return self._executor

    @property
    def exchangeinfo_cache(self) -> Any:
        """Get exchange info cache (lazy-loaded)."""
        if self._exchange_cache is None:
            from tezaver.bulut.services.exchangeinfo_cache import ExchangeInfoCache
            self._exchange_cache = ExchangeInfoCache(self.config, self.telemetry)
        return self._exchange_cache

    @property
    def rate_limit_governor(self) -> Any:
        """Get rate limit governor (lazy-loaded)."""
        if self._governor is None:
            from tezaver.bulut.services.rate_limit_governor import RateLimitGovernor
            self._governor = RateLimitGovernor(self.config, self.telemetry)
        return self._governor

    @property
    def group_caps_loader(self) -> Any:
        if self._group_caps is None:
            from tezaver.bulut.services.group_caps_loader import GroupCapsLoader
            self._group_caps = GroupCapsLoader(self.config)
        return self._group_caps
        
    @property
    def time_sync(self) -> Any:
        if self._time_sync is None:
            from tezaver.bulut.services.time_sync import TimeSyncService
            self._time_sync = TimeSyncService(self.config, self.telemetry)
        return self._time_sync

    @property
    def portfolio_risk(self) -> Any:
        if self._risk is None:
            from tezaver.bulut.services.portfolio_risk import PortfolioRiskService
            self._risk = PortfolioRiskService(
                self.config,
                self.persistence,
                self.group_caps_loader,
                self.telemetry
            )
        return self._risk

    @property
    def decider(self) -> Any:
        """Get decider engine (lazy-loaded)."""
        if getattr(self, "_decider", None) is None:
            from tezaver.bulut.engine.decider import Decider
            self._decider = Decider(self, risk_service=self.portfolio_risk)
        return self._decider

    @property
    def reconciliation_service(self) -> Any:
        """Get reconciliation service (lazy-loaded)."""
        if getattr(self, "_reconciler", None) is None:
            from tezaver.bulut.services.reconciliation import ReconciliationService
            self._reconciler = ReconciliationService(self)
        return self._reconciler

    @property
    def exit_profile_loader(self) -> Any:
        """Get exit profile loader (lazy-loaded)."""
        if getattr(self, "_exit_loader", None) is None:
            from tezaver.bulut.services.exit_profile_loader import ExitProfileLoader
            self._exit_loader = ExitProfileLoader(self._config)
        return self._exit_loader

    @property
    def exit_engine(self) -> Any:
        """Get exit engine (lazy-loaded)."""
        if getattr(self, "_exit_engine", None) is None:
            from tezaver.bulut.engine.exit_engine import ExitEngine
            self._exit_engine = ExitEngine(self._config)
        return self._exit_engine

    @property
    def status_service(self) -> Any:
        if self._status_service is None:
            from tezaver.bulut.services.status_service import StatusService
            self._status_service = StatusService(self.config)
        return self._status_service

    @property
    def incident_bundle(self) -> Any:
        if self._incident_bundle is None:
            from tezaver.bulut.services.incident_bundle import IncidentBundleService
            # We use 'data/bulut_incidents' as default export dir
            self._incident_bundle = IncidentBundleService("data/bulut_incidents")
        return self._incident_bundle

    @property
    def fill_sync(self) -> Any:
        if getattr(self, "_fill_sync", None) is None:
            from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
            from tezaver.bulut.services.fill_sync import FillSyncService
            
            # Create dedicated client for fill sync
            # Note: Ideally share session, but separate instance is safer for lazy load
            client = BinanceFuturesSigned(self.config, self.rate_limit_governor, self.time_sync)
            
            self._fill_sync = FillSyncService(
                self.config,
                client,
                self.telemetry,
                self.persistence, 
                self.time_sync
            )
            self._fill_sync = FillSyncService(
                self.config,
                client,
                self.telemetry,
                self.persistence, 
                self.time_sync,
                self.fx_rate_cache # Inject FX Cache
            )
        return self._fill_sync

    @property
    def income_sync(self) -> Any:
        if getattr(self, "_income_sync", None) is None:
            from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
            from tezaver.bulut.services.income_sync import IncomeSyncService
            
            client = BinanceFuturesSigned(self.config, self.rate_limit_governor, self.time_sync)
            
            self._income_sync = IncomeSyncService(
                self.config,
                client,
                self.persistence,
                self.telemetry,
                self.time_sync,
                # Inject FX Cache if needed? 
                # Actually IncomeSyncService needs to use cache.
                # But IncomeSyncService constructor above doesn't have it yet.
                # We need to update IncomeSyncService to accept it.
                # For now, let's inject it via property or update constructor later in this plan.
                self.fx_rate_cache 
            )
        return self._income_sync

    @property
    def fx_rate_cache(self) -> Any:
        if getattr(self, "_fx_cache", None) is None:
            from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
            from tezaver.bulut.services.fx_rate_cache import FxRateCache
            
            # Use shared or new client? Market data client.
            client = BinanceFuturesSigned(self.config, self.rate_limit_governor, self.time_sync)
            
            self._fx_cache = FxRateCache(
                self.config,
                client,
                self.persistence,
                self.telemetry
            )
        return self._fx_cache

    @property
    def fx_recompute(self) -> Any:
        if getattr(self, "_fx_recompute", None) is None:
            from tezaver.bulut.services.fx_recompute import FxRecomputeService
            self._fx_recompute = FxRecomputeService(
                self.config,
                self.fx_rate_cache,
                self.persistence,
                self.telemetry
            )
        return self._fx_recompute

    @property
    def env_doctor(self) -> Any:
        if getattr(self, "_env_doctor", None) is None:
            from tezaver.bulut.services.env_doctor import EnvDoctor
            self._env_doctor = EnvDoctor(self.config, self.telemetry)
        return self._env_doctor

    @property
    def user_data_stream(self) -> Any:
        if getattr(self, "_user_data_stream", None) is None:
            from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
            from tezaver.bulut.services.user_data_stream import UserDataStream
            
            # Use dedicated client or shared?
            # Reusing client from FillSync or creating new?
            # Creating new one for stream management is cleaner.
            client = BinanceFuturesSigned(self.config, self.rate_limit_governor, self.time_sync)
            
            self._user_data_stream = UserDataStream(
                self.config,
                client,
                self.telemetry
            )
            # v0.22 Inject Reducer
            self._user_data_stream.set_reducer(self.state_reducer)
            
        return self._user_data_stream

    @property
    def state_reducer(self) -> Any:
        if getattr(self, "_state_reducer", None) is None:
            from tezaver.bulut.services.state_reducer import StateReducer
            self._state_reducer = StateReducer(
                self.config,
                self.persistence,
                self.telemetry
            )
        return self._state_reducer

    @property
    def task_supervisor(self) -> Any:
        if getattr(self, "_task_supervisor", None) is None:
            from tezaver.bulut.services.task_supervisor import TaskSupervisor
            self._task_supervisor = TaskSupervisor(
                self.config,
                self.persistence,
                self.telemetry
            )
        return self._task_supervisor

    @property
    def launch_checklist(self) -> Any:
        if getattr(self, "_launch_checklist", None) is None:
            from tezaver.bulut.services.launch_checklist import LaunchChecklist
            self._launch_checklist = LaunchChecklist(self.config, self.telemetry)
        return self._launch_checklist

    @property
    def config_snapshot(self) -> Any:
        if getattr(self, "_config_snapshot", None) is None:
            from tezaver.bulut.services.config_snapshot import ConfigSnapshotService
            self._config_snapshot = ConfigSnapshotService()
        return self._config_snapshot

    @property
    def drift_guard(self) -> Any:
        if getattr(self, "_drift_guard", None) is None:
            from tezaver.bulut.services.drift_guard import DriftGuard
            self._drift_guard = DriftGuard(self)
        return self._drift_guard

    @property
    def migration_runner(self) -> Any:
        if getattr(self, "_migration_runner", None) is None:
            from tezaver.bulut.services.migration_runner import MigrationRunner
            self._migration_runner = MigrationRunner(self.persistence)
        return self._migration_runner

    @property
    def constitution_guard(self) -> Any:
        if getattr(self, "_constitution_guard", None) is None:
            from tezaver.bulut.services.constitution_guard import ConstitutionGuard
            self._constitution_guard = ConstitutionGuard(self)
        return self._constitution_guard

    @property
    def policy(self) -> Any:
        """Get policy state machine (lazy-loaded)."""
        if getattr(self, "_policy", None) is None:
            from tezaver.bulut.engine.policy_state_machine import PolicyStateMachine
            self._policy = PolicyStateMachine(self.config)
        return self._policy

    @property
    def proof_ladder(self) -> Any:
        """Get proof ladder service (lazy-loaded)."""
        if getattr(self, "_proof_ladder", None) is None:
            from tezaver.bulut.services.proof_ladder import ProofLadderService
            self._proof_ladder = ProofLadderService(self)
        return self._proof_ladder

    @property
    def strict_timing(self) -> Any:
        """Get strict timing service (lazy-loaded)."""
        if getattr(self, "_strict_timing", None) is None:
            from tezaver.bulut.core.strict_timing_service import StrictTimingService
            self._strict_timing = StrictTimingService(self.persistence, self.config, self.telemetry)
        return self._strict_timing
        
    @property
    def dry_run_service(self) -> Any:
        """Get dry run service (lazy-loaded)."""
        if getattr(self, "_dry_run_service", None) is None:
            from tezaver.bulut.core.dry_run_service import DryRunService
            self._dry_run_service = DryRunService(self)
        return self._dry_run_service

    @property
    def pilot_meter(self) -> Any:
        """Get pilot meter service (lazy-loaded)."""
        if getattr(self, "_pilot_meter", None) is None:
            from tezaver.bulut.core.pilot_meter import PilotMeter
            # P6: Inject expansion policy for dynamic tier limits
            self._pilot_meter = PilotMeter(self.persistence, self.expansion_policy)
        return self._pilot_meter

    @property
    def expansion_policy(self) -> Any:
        """Get expansion policy service (lazy-loaded)."""
        if getattr(self, "_expansion_policy", None) is None:
            from tezaver.bulut.core.expansion_policy import ExpansionPolicyService
            self._expansion_policy = ExpansionPolicyService(self)
        return self._expansion_policy

    @property
    def autopilot_service(self) -> Any:
        """Get autopilot service (lazy-loaded)."""
        if getattr(self, "_autopilot_service", None) is None:
            from tezaver.bulut.core.autopilot_service import AutopilotService
            self._autopilot_service = AutopilotService(self)
        return self._autopilot_service

    @property
    def allocation_engine(self) -> Any:
        """Get allocation engine (lazy-loaded)."""
        if getattr(self, "_allocation_engine", None) is None:
            from tezaver.bulut.core.allocation_engine import AllocationEngine
            self._allocation_engine = AllocationEngine(self)
        return self._allocation_engine

    def check_trade_lock(self) -> tuple[bool, Optional[str]]:
        """
        Checks if trading should be locked based on various conditions.
        Returns a tuple: (is_locked, reason_if_locked)
        """
        # Rule 0: Startup Self-Test Failed (v0.20)
        if self._state.startup_degraded:
            return True, "STARTUP_SELFTEST_FAIL"

        # Rule 1: Pattern pack must be loaded
        if not self._state.pattern_pack_loaded:
            return True, "PATTERN_PACK_MISSING"
        
        # Rule 2: Position limit check
        if self._state.open_positions_count >= self._config.max_open_positions:
            return True, "MAX_POSITIONS_REACHED"
        
        # Rule 3: Notional limit check
        max_notional = self._config.max_total_notional_usdt
        # v1.1 Proof Ladder Override (Real Mainnet)
        if self._config.mode == "REAL_MAINNET" and self._config.proof_ladder_enabled:
             # Ensure proof_ladder service available (lazy load)
             # But calling method computes effective.
             max_notional = self.proof_ladder.compute_effective_mainnet_cap()
             
        if self._state.total_notional_usdt >= max_notional:
            return True, "MAX_NOTIONAL_REACHED"
        
        return False, None
    
    def update_trade_lock(self) -> None:
        """Update trade lock state based on current conditions."""
        locked, reason = self.check_trade_lock()
        self._state.trade_locked = locked
        self._state.trade_lock_reason = reason
    
    def load_pattern_pack(self) -> bool:
        """
        Load latest pattern pack if available.
        
        Returns:
            True if loaded successfully, False otherwise.
        """
        pack = self.pattern_loader.load_latest_parsed()
        if pack is None:
            self._state.pattern_pack_loaded = False
            self._state.pattern_pack_id = None
            self._state.pattern_pack_hash = None
            self.update_trade_lock()
            return False
        
        self._state.pattern_pack_loaded = True
        # pack is PatternPackV1 object, so access attributes directly
        self._state.pattern_pack_id = getattr(pack, "pack_id", None)
        self._state.pattern_pack_hash = getattr(pack, "hash", None)
        self.update_trade_lock()
        return True


# Global context instance (lazy-loaded)
_context: Optional[BulutContext] = None


def get_context() -> BulutContext:
    """Get or create global context instance."""
    global _context
    if _context is None:
        _context = BulutContext()
    return _context


def bootstrap_context(config: Optional[BulutConfig] = None) -> BulutContext:
    """Bootstrap context with optional custom config."""
    global _context
    _context = BulutContext(config)
    return _context
