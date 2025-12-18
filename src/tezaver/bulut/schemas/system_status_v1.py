# Tezaver Bulut - System Status Schema (v1)
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class DaemonStatus:
    running: bool
    last_cycle_ts: Optional[str] = None
    last_cycle_duration_ms: float = 0.0
    last_partial_ingest: bool = False

@dataclass
class TimeSyncStatus:
    healthy: bool
    offset_ms: int
    last_sync_ts: Optional[str] = None
    last_error: Optional[str] = None

@dataclass
class ExchangeInfoStatus:
    fresh: bool
    age_s: float
    symbols_count: int

@dataclass
class RateLimitStatus:
    market_used: int
    market_budget: int
    trade_used: int
    trade_budget: int

@dataclass
class RiskStatus:
    today_pnl: float
    daily_limit: float
    entry_halted: bool

@dataclass
class ExecutionStatus:
    enabled: bool
    armed: bool
    mode: str
    last_exec_state_counts: Dict[str, int] = field(default_factory=dict)

@dataclass
class ReconciliationStatus:
    last_run_ts: Optional[str] = None
    last_orphans_count: int = 0

@dataclass
class SystemStatusV1:
    ts: str
    daemon: DaemonStatus
    time_sync: TimeSyncStatus
    exchangeinfo: ExchangeInfoStatus
    rate_limit: RateLimitStatus
    risk: RiskStatus
    execution: ExecutionStatus
    reconciliation: ReconciliationStatus
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ts": self.ts,
            "daemon": self.daemon.__dict__,
            "time_sync": self.time_sync.__dict__,
            "exchangeinfo": self.exchangeinfo.__dict__,
            "rate_limit": self.rate_limit.__dict__,
            "risk": self.risk.__dict__,
            "execution": self.execution.__dict__,
            "reconciliation": self.reconciliation.__dict__
        }
