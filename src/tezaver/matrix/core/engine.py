# Matrix V2 Engine Module
"""
Core engine protocols and UnifiedEngine for Matrix v2.
"""

from __future__ import annotations
from typing import Protocol, TYPE_CHECKING
from datetime import datetime
import uuid

from .types import MarketSignal, TradeDecision, ExecutionReport, MatrixEventLogEntry
from .account import AccountState, IAccountStore

if TYPE_CHECKING:
    from .guardrail import GuardrailController


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
    """
    
    def __init__(
        self,
        profile_id: str,
        analyzer: IAnalyzer,
        strategist: IStrategist,
        executor: IExecutor,
        guardrail: "GuardrailController",
        account_store: IAccountStore,
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
        """
        self.profile_id = profile_id
        self.analyzer = analyzer
        self.strategist = strategist
        self.executor = executor
        self.guardrail = guardrail
        self.account_store = account_store
    
    def tick(self, market_snapshot: dict) -> list[MatrixEventLogEntry]:
        """
        Process a single tick of market data through the trading pipeline.
        
        Pipeline:
        1. Analyzer generates signals from market data
        2. Strategist evaluates signals and creates decisions
        3. Guardrail validates decisions against risk rules
        4. Executor executes approved decisions
        5. Account state is updated
        
        Args:
            market_snapshot: Dictionary containing current market data.
            
        Returns:
            List of MatrixEventLogEntry for audit trail.
        """
        events: list[MatrixEventLogEntry] = []
        timestamp = datetime.now()
        
        # Step 1: Load account state
        account = self.account_store.load_account(self.profile_id)
        
        # Step 2: Analyze market
        signals = self.analyzer.analyze(market_snapshot)
        
        # Log signals
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
                continue
            
            # Log decision
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
            
            # Step 4: Check guardrail
            guardrail_decision = self.guardrail.check_new_trade(
                self.profile_id, account, decision
            )
            
            if not guardrail_decision.allow:
                # Log guardrail rejection
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
            report = self.executor.execute(decision, account, market_snapshot)
            
            # Log execution
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
        
        return events
