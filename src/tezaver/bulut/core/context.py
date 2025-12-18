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
            self._pattern_loader = PatternPackLoader(self._config.pattern_pack_dir)
        return self._pattern_loader

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
            from tezaver.bulut.engine.executor import Executor
            self._executor = Executor(self.config, governor=self.rate_limit_governor)
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
            self._decider = Decider(self.config, risk_service=self.portfolio_risk)
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

    def check_trade_lock(self) -> tuple[bool, Optional[str]]:
        """
        Checks if trading should be locked based on various conditions.
        Returns a tuple: (is_locked, reason_if_locked)
        """
        # Rule 1: Pattern pack must be loaded
        if not self._state.pattern_pack_loaded:
            return True, "PATTERN_PACK_MISSING"
        
        # Rule 2: Position limit check
        if self._state.open_positions_count >= self._config.max_open_positions:
            return True, "MAX_POSITIONS_REACHED"
        
        # Rule 3: Notional limit check
        if self._state.total_notional_usdt >= self._config.max_total_notional_usdt:
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
        pack = self.pattern_loader.load_latest()
        if pack is None:
            self._state.pattern_pack_loaded = False
            self._state.pattern_pack_id = None
            self._state.pattern_pack_hash = None
            self.update_trade_lock()
            return False
        
        self._state.pattern_pack_loaded = True
        self._state.pattern_pack_id = pack.get("pack_id")
        self._state.pattern_pack_hash = pack.get("hash")
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
