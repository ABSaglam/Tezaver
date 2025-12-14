# Matrix V2 Engine Module
"""
Core engine protocols and UnifiedEngine for Matrix v2.

Supports profile-aware guardrail with CoinPage V2 integration.
"""

from __future__ import annotations
from typing import Protocol, TYPE_CHECKING, Optional, Dict, Any
from datetime import datetime
import uuid

from .types import MarketSignal, TradeDecision, ExecutionReport, MatrixEventLogEntry
from .account import AccountState, IAccountStore
from .guardrail import (
    GuardrailController,
    GuardrailContext,
    GuardrailEnvironment,
)
from .telemetry import (
    MatrixEvent,
    MatrixEventType,
    IMatrixEventSink,
)

if TYPE_CHECKING:
    from .profile import MatrixProfileRepository, MatrixCellProfile


class IAnalyzer(Protocol):
    """
    Protocol for market analysis components.
    
    Analyzers examine market data and generate signals.
    """
    
    def analyze(self, market_snapshot: dict) -> list[MarketSignal]:
        """
        Analyze market snapshot and return list of detected signals.
        
        Args:
            market_snapshot: Dictionary containing OHLCV and indicator data.
            
        Returns:
            List of MarketSignal objects representing detected conditions.
        """
        ...


class IStrategist(Protocol):
    """
    Protocol for strategy evaluation components.
    
    Strategists evaluate signals and make trading decisions.
    """
    
    def evaluate(self, signal: MarketSignal, account: AccountState) -> TradeDecision | None:
        """
        Evaluate a signal and decide whether to trade.
        
        Args:
            signal: The market signal to evaluate.
            account: Current account state for position sizing.
            
        Returns:
            TradeDecision if action should be taken, None otherwise.
        """
        ...


class IExecutor(Protocol):
    """
    Protocol for trade execution components.
    
    Executors handle the actual order placement and fills.
    """
    
    def execute(
        self,
        decision: TradeDecision,
        account: AccountState,
        market_snapshot: dict | None = None,
    ) -> ExecutionReport:
        """
        Execute a trading decision.
        
        Args:
            decision: The trade decision to execute.
            account: Current account state for validation.
            market_snapshot: Optional market snapshot for simulation PnL.
            
        Returns:
            ExecutionReport with fill details or error.
        """
        ...


class UnifiedEngine:
    """
    Unified trading engine that orchestrates the Analyzer-Strategist-Executor pipeline.
    
    This is the main entry point for processing market data through the
    Matrix trading system.
    
    V2: Supports profile-aware guardrail with CoinPage V2 integration.
    """
    
    def __init__(
        self,
        profile_id: str,
        analyzer: IAnalyzer,
        strategist: IStrategist,
        executor: IExecutor,
        guardrail: GuardrailController,
        account_store: IAccountStore,
        # V2 fields for profile-aware guardrail
        symbol: str = "",
        timeframe: str = "",
        environment: GuardrailEnvironment = GuardrailEnvironment.WARGAME,
        profile_repo: Optional["MatrixProfileRepository"] = None,
        # V3 telemetry
        event_sink: Optional[IMatrixEventSink] = None,
    ) -> None:
        """
        Initialize the UnifiedEngine.
        
        Args:
            profile_id: Unique identifier for this trading profile.
            analyzer: Component for market analysis.
            strategist: Component for trading decisions.
            executor: Component for order execution.
            guardrail: Controller for risk management rules.
            account_store: Storage for account state.
            symbol: Trading symbol (e.g., "BTCUSDT") for guardrail context.
            timeframe: Timeframe (e.g., "15m") for guardrail context.
            environment: WARGAME or LIVE for guardrail decisions.
            profile_repo: Repository for loading profiles (for profile-aware guardrail).
            event_sink: Optional telemetry sink for event logging.
        """
        self.profile_id = profile_id
        self.analyzer = analyzer
        self.strategist = strategist
        self.executor = executor
        self.guardrail = guardrail
        self.account_store = account_store
        # V2 fields
        self.symbol = symbol
        self.timeframe = timeframe
        self.environment = environment
        self.profile_repo = profile_repo
        # V3 telemetry
        self._event_sink = event_sink
        self._tick_index = 0
    
    def _log_event(
        self,
        event_type: MatrixEventType,
        details: Dict[str, Any],
    ) -> None:
        """Log event to telemetry sink if available."""
        if self._event_sink is None:
            return
        
        event = MatrixEvent(
            event_type=event_type,
            symbol=self.symbol,
            timeframe=self.timeframe,
            profile_id=self.profile_id,
            environment=self.environment,
            ts=datetime.now(),
            tick_index=self._tick_index,
            details=details,
        )
        self._event_sink.log(event)
    
    def tick(self, market_snapshot: dict) -> list[MatrixEventLogEntry]:
        """
        Process a single tick of market data through the trading pipeline.
        
        Pipeline:
        1. Analyzer generates signals from market data
        2. Strategist evaluates signals and creates decisions
        3. Guardrail validates decisions against risk rules (profile-aware)
        4. Executor executes approved decisions
        5. Account state is updated
        
        Args:
            market_snapshot: Dictionary containing current market data.
            
        Returns:
            List of MatrixEventLogEntry for audit trail.
        """
        events: list[MatrixEventLogEntry] = []
        timestamp = datetime.now()
        
        # Telemetry: TICK_START
        self._log_event(MatrixEventType.TICK_START, {"note": "tick start"})
        
        # Step 1: Load account state
        account = self.account_store.load_account(self.profile_id)
        
        # Step 2: Analyze market
        signals = self.analyzer.analyze(market_snapshot)
        
        # Telemetry: SIGNAL (summary)
        self._log_event(MatrixEventType.SIGNAL, {
            "signal_count": len(signals),
            "signals": [
                {"type": s.signal_type, "confidence": s.confidence}
                for s in signals[:3]  # Max 3 for brevity
            ],
        })
        
        # Log signals (legacy MatrixEventLogEntry)
        for signal in signals:
            events.append(
                MatrixEventLogEntry(
                    event_id=str(uuid.uuid4()),
                    profile_id=self.profile_id,
                    event_type="SIGNAL",
                    timestamp=timestamp,
                    payload={
                        "signal_id": signal.signal_id,
                        "signal_type": signal.signal_type,
                        "direction": signal.direction,
                        "confidence": signal.confidence,
                    },
                    severity="info",
                )
            )
        
        # Step 3: Evaluate signals and get decisions
        for signal in signals:
            decision = self.strategist.evaluate(signal, account)
            if decision is None:
                # Telemetry: DECISION (no trade)
                self._log_event(MatrixEventType.DECISION, {
                    "decision": None,
                    "reason": "no_trade",
                })
                continue
            
            # Telemetry: DECISION
            self._log_event(MatrixEventType.DECISION, {
                "action": decision.action,
                "quantity": getattr(decision, "quantity", None),
                "tp_pct": getattr(decision, "tp_pct", None),
                "sl_pct": getattr(decision, "sl_pct", None),
            })
            
            # Log decision (legacy)
            events.append(
                MatrixEventLogEntry(
                    event_id=str(uuid.uuid4()),
                    profile_id=self.profile_id,
                    event_type="DECISION",
                    timestamp=timestamp,
                    payload={
                        "decision_id": decision.decision_id,
                        "signal_id": decision.signal_id,
                        "action": decision.action,
                        "reason": decision.reason,
                    },
                    severity="info",
                )
            )
            
            # Step 4a: Check profile-aware guardrail (V2)
            if self.guardrail is not None and self.profile_repo is not None:
                ctx = GuardrailContext(
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    profile_id=self.profile_id,
                    environment=self.environment,
                    risk_per_trade_requested=getattr(decision, "risk_per_trade", None),
                )
                
                profile: Optional["MatrixCellProfile"] = None
                if self.profile_id:
                    profile = self.profile_repo.get_profile(self.profile_id)
                
                g_decision = self.guardrail.check_profile_and_risk(profile, ctx)
                
                # Telemetry: GUARDRAIL_V2
                self._log_event(MatrixEventType.GUARDRAIL_V2, {
                    "allow": g_decision.allow,
                    "reason_code": g_decision.reason_code,
                    "profile_status": g_decision.profile_status,
                    "risk_contract_max": g_decision.risk_contract_max,
                })
                
                # Log profile-aware guardrail decision (legacy)
                events.append(
                    MatrixEventLogEntry(
                        event_id=str(uuid.uuid4()),
                        profile_id=self.profile_id,
                        event_type="GUARDRAIL_V2",
                        timestamp=timestamp,
                        payload={
                            "allow": g_decision.allow,
                            "reason_code": g_decision.reason_code,
                            "profile_status": g_decision.profile_status,
                            "risk_contract_max": g_decision.risk_contract_max,
                        },
                        severity="info" if g_decision.allow else "warning",
                    )
                )
                
                if not g_decision.allow:
                    # Trade blocked by profile-aware guardrail
                    continue
            
            # Step 4b: Check classic guardrail (position limits, daily loss, etc.)
            guardrail_decision = self.guardrail.check_new_trade(
                self.profile_id, account, decision
            )
            
            # Telemetry: GUARDRAIL_V1
            self._log_event(MatrixEventType.GUARDRAIL_V1, {
                "allow": guardrail_decision.allow,
                "reason_code": guardrail_decision.reason_code,
            })
            
            if not guardrail_decision.allow:
                # Log guardrail rejection (legacy)
                events.append(
                    MatrixEventLogEntry(
                        event_id=str(uuid.uuid4()),
                        profile_id=self.profile_id,
                        event_type="GUARDRAIL",
                        timestamp=timestamp,
                        payload={
                            "decision_id": decision.decision_id,
                            "allow": False,
                            "reason_code": guardrail_decision.reason_code,
                            "details": guardrail_decision.details,
                        },
                        severity="warning",
                    )
                )
                continue
            
            # Step 5: Execute if allowed (pass market_snapshot for PnL)
            equity_before = account.capital
            report = self.executor.execute(decision, account, market_snapshot)
            equity_after = self.account_store.load_account(self.profile_id).capital
            
            # Telemetry: EXECUTION
            self._log_event(MatrixEventType.EXECUTION, {
                "status": report.status,
                "executed_price": report.executed_price,
                "executed_quantity": report.executed_quantity,
                "pnl": getattr(report, "pnl", None),
                "equity_before": equity_before,
                "equity_after": equity_after,
            })
            
            # Log execution (legacy)
            events.append(
                MatrixEventLogEntry(
                    event_id=str(uuid.uuid4()),
                    profile_id=self.profile_id,
                    event_type="EXECUTION",
                    timestamp=timestamp,
                    payload={
                        "execution_id": report.execution_id,
                        "decision_id": report.decision_id,
                        "status": report.status,
                        "executed_price": report.executed_price,
                        "executed_quantity": report.executed_quantity,
                    },
                    severity="info" if report.status == "filled" else "warning",
                )
            )
            
            # Reload account state after execution (executor updates equity)
            account = self.account_store.load_account(self.profile_id)
        
        # Telemetry: TICK_END
        self._log_event(MatrixEventType.TICK_END, {"note": "tick end"})
        self._tick_index += 1
        
        return events


