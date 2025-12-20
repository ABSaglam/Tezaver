# Matrix V2 Sim Executor
"""
Simulation executor that calculates PnL based on future_max_gain_pct and future_min_drawdown_pct.

Stop-loss logic:
- If future drawdown exceeds SL → trade loses
- If both TP and SL are hit → SL takes priority (conservative)
"""

from datetime import datetime
import uuid

from ..core.engine import IExecutor
from ..core.types import TradeDecision, ExecutionReport
from ..core.account import AccountState


class SimExecutor(IExecutor):
    """
    Simulation executor that calculates real PnL from market snapshot labels.
    
    Uses future_max_gain_pct and future_min_drawdown_pct to determine trade outcome:
    - If future drawdown exceeds SL → loss at SL
    - If future gain exceeds TP (and no SL hit) → win at TP
    - If both hit → SL priority (conservative worst-case)
    - Otherwise → horizon exit at future_gain
    """
    
    def __init__(self, account_store: "WargameAccountStore") -> None:
        """
        Initialize SimExecutor with account store.
        
        Args:
            account_store: WargameAccountStore for equity updates.
        """
        self._account_store = account_store
    
    def execute(
        self,
        decision: TradeDecision,
        account: AccountState,
        market_snapshot: dict | None = None,
    ) -> ExecutionReport:
        """
        Execute a trade decision using simulated PnL from snapshot.
        
        Stop-loss logic:
        - stop_hit: future_min_drawdown_pct <= -sl_pct
        - tp_hit: future_max_gain_pct >= tp_pct
        - If stop_hit and not tp_hit → SL loss
        - If tp_hit and not stop_hit → TP win
        - If both hit → SL priority (conservative)
        - Otherwise → horizon exit at future_gain
        
        Args:
            decision: The trade decision to execute.
            account: Current account state.
            market_snapshot: Market snapshot containing future_max_gain_pct and future_min_drawdown_pct.
            
        Returns:
            ExecutionReport with fill details.
        """
        # Only process open_long actions
        if decision.action != "open_long":
            return ExecutionReport(
                execution_id=str(uuid.uuid4()),
                decision_id=decision.decision_id,
                symbol=decision.symbol,
                status="rejected",
                executed_price=None,
                executed_quantity=None,
                commission=0.0,
                timestamp=datetime.now(),
                error_message="Only open_long supported",
                metadata={"reason": "non_buy_ignored"},
            )
        
        # Get current equity
        equity_before = self._account_store.get_equity()
        
        # Get future gain and drawdown from snapshot
        future_gain = 0.0
        future_dd = 0.0
        if market_snapshot:
            fg = market_snapshot.get("future_max_gain_pct")
            if fg is not None:
                future_gain = float(fg)
            
            fdd = market_snapshot.get("future_min_drawdown_pct")
            if fdd is not None:
                future_dd = float(fdd)  # Usually negative, e.g., -0.03 = -3% drawdown
        
        # Get TP/SL from decision metadata
        tp_pct = decision.metadata.get("tp_pct") or 0.0
        sl_pct = decision.metadata.get("sl_pct") or 0.0
        tp_pct = float(tp_pct)
        sl_pct = float(sl_pct)
        
        # --- STOP / TP / HORIZON LOGIC ---
        # stop_hit: future drawdown went below -SL (e.g., -5% drawdown with 2% SL)
        stop_hit = sl_pct > 0.0 and future_dd <= -sl_pct
        # tp_hit: future gain reached TP level
        tp_hit = tp_pct > 0.0 and future_gain >= tp_pct
        
        # Default: horizon exit at future_gain
        pnl_pct = future_gain
        exit_reason = "horizon"
        
        if stop_hit and not tp_hit:
            # SL hit, TP not reached → loss at SL
            pnl_pct = -sl_pct
            exit_reason = "stop_loss"
        elif tp_hit and not stop_hit:
            # TP hit, SL not touched → win at TP
            pnl_pct = tp_pct
            exit_reason = "take_profit"
        elif stop_hit and tp_hit:
            # Both hit - we don't know order, assume SL first (conservative)
            pnl_pct = -sl_pct
            exit_reason = "stop_loss_priority"
        # else: neither hit → use future_gain as horizon exit
        
        # Calculate PnL based on position size
        position_size = decision.position_size or equity_before
        pnl = position_size * pnl_pct
        equity_after = equity_before + pnl
        
        # Apply to account store
        exec_event = {
            "event_type": "TRADE",
            "profile_id": decision.decision_id,
            "symbol": decision.symbol,
            "pnl_pct": pnl_pct,
            "pnl": pnl,
            "capital_before": equity_before,
            "capital_after": equity_after,
            "future_max_gain_pct": future_gain,
            "future_min_drawdown_pct": future_dd,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "exit_reason": exit_reason,
            "timestamp": datetime.now().isoformat(),
        }
        self._account_store.apply_execution(exec_event)
        
        return ExecutionReport(
            execution_id=str(uuid.uuid4()),
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            status="filled",
            executed_price=market_snapshot.get("close") if market_snapshot else None,
            executed_quantity=position_size,
            commission=0.0,
            timestamp=datetime.now(),
            error_message=None,
            metadata={
                "pnl_pct": pnl_pct,
                "pnl": pnl,
                "equity_after": equity_after,
                "exit_reason": exit_reason,
            },
        )

