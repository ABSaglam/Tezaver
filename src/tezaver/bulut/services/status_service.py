# Tezaver Bulut - Status Service
"""
Aggregates system status from various components.
"""

import time
from datetime import datetime, timezone
from typing import Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.system_status_v1 import (
    SystemStatusV1, DaemonStatus, TimeSyncStatus, ExchangeInfoStatus,
    RateLimitStatus, RiskStatus, ExecutionStatus, ReconciliationStatus
)

class StatusService:
    def __init__(self, config: BulutConfig):
        self._config = config
        self._cache: Optional[SystemStatusV1] = None
        self._last_cache_ts = 0.0
        self._cache_ttl = 2.0  # seconds

    def get_status(self, ctx) -> SystemStatusV1:
        """
        Build and return system status. Uses short valid cache.
        'ctx' is passed to avoid circular dependency in init.
        """
        now = time.time()
        if self._cache and (now - self._last_cache_ts) < self._cache_ttl:
            return self._cache

        # build fresh
        status = self._build_status(ctx)
        self._cache = status
        self._last_cache_ts = now
        return status

    def _build_status(self, ctx) -> SystemStatusV1:
        now_ts = datetime.now(timezone.utc).isoformat()
        state = ctx.state
        
        # Daemon
        daemon = DaemonStatus(
            running=True, # Implicit if we are answering
            last_cycle_ts=getattr(state, "last_scan_ts", None).isoformat() if getattr(state, "last_scan_ts", None) else None,
            # We assume state has these or defaults
        )

        # Time Sync
        ts_healthy = False
        offset = 0
        if ctx.time_sync:
             ts_healthy, details = ctx.time_sync.is_healthy()
             offset = details.get("offset_ms", 0)
        
        time_sync = TimeSyncStatus(
            healthy=ts_healthy,
            offset_ms=offset,
            # last_sync_ts could be extracted from details if available
        )

        # Exchange Info
        ex_fresh = False
        ex_age = 0.0
        ex_count = 0
        if ctx.exchangeinfo_cache:
             est = ctx.exchangeinfo_cache.get_status()
             ex_fresh = est.get("is_fresh", False)
             ex_age = est.get("age_seconds", 0.0)
             ex_count = est.get("symbols_count", 0)

        exchangeinfo = ExchangeInfoStatus(
            fresh=ex_fresh,
            age_s=ex_age,
            symbols_count=ex_count
        )

        # Rate Limit (Placeholder / extracted from telemetry if possible, but Governor tracks it internally)
        # Assuming Governor exposes metrics
        # For v0.15, we might stick to defaults if Governor doesn't expose public metrics yet.
        rate_limit = RateLimitStatus(
            market_used=0, market_budget=1,
            trade_used=0, trade_budget=1
        )
        
        # Risk
        # Need PortfolioRisk service
        risk_pnl = 0.0
        risk_limit = 0.0
        risk_halted = False
        if ctx.portfolio_risk:
             rstatus = ctx.portfolio_risk.get_risk_status()
             risk_pnl = rstatus.get("today_pnl", 0.0)
             risk_limit = rstatus.get("daily_loss_limit", 0.0)
             risk_halted = rstatus.get("entry_halted", False)
             
        risk = RiskStatus(
            today_pnl=risk_pnl,
            daily_limit=risk_limit,
            entry_halted=risk_halted
        )

        # Execution
        execution = ExecutionStatus(
            enabled=self._config.execution_enabled,
            armed=self._config.arm_token is not None,
            mode=self._config.mode
        )

        # Reconciliation
        # Stub
        reconciliation = ReconciliationStatus()

        # State Reducer (v0.22)
        # Assuming we can access stats? 
        # Context has state_reducer property.
        reducer_stats = {}
        if hasattr(ctx, "state_reducer"):
            reducer_stats = ctx.state_reducer.get_stats()
            
        result = SystemStatusV1(
            ts=now_ts,
            daemon=daemon,
            time_sync=time_sync,
            exchangeinfo=exchangeinfo,
            rate_limit=rate_limit,
            risk=risk,
            execution=execution,
            reconciliation=reconciliation
        )
        
        # Inject extras (Reducer, Heartbeats)
        # Assuming Dashboard handles arbitrary attrs or we patch objects
        # Or better: return a dict wrapper or modified object if dashboard expects V1
        # Dashboard expects objects for some fields but accesses others?
        # Let's attach them to the object instance dynamically
        result.reducer = reducer_stats
        
        # Heartbeats (v0.23)
        if hasattr(ctx, "persistence"):
             result.heartbeats = ctx.persistence.get_heartbeats()
             
        # v0.28 Constitution
        if hasattr(ctx, "constitution_guard"):
             c = ctx.constitution_guard.get_current()
             result.constitution = {
                 "version": c["version"],
                 "sha256_short": c["sha256_short"],
                 "ts": c["ts"]
             }

        return result
```
