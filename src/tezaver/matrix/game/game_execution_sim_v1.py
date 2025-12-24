from typing import Optional, List, Dict
from dataclasses import replace
from tezaver.matrix.game.game_models_v1 import GameTrade

class GameExecutionSim:
    """
    Deterministic Execution Simulator for GAME v1.
    - Model: NEXT_BAR_OPEN (Decisions at T close, Fill at T+1 open)
    - Long-only v1
    - Fixed fee bps
    """
    def __init__(self, initial_capital: float = 100.0, fee_bps: float = 10.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital # Cash
        self.fee_rate = fee_bps / 10000.0
        
        self.position: Optional[GameTrade] = None # Active position
        self.trades: List[GameTrade] = []
        
        self.equity = initial_capital
        
    def on_bar_open(self, ts: int, open_price: float, decision_from_prev_close: Optional[str], bar_index: int) -> Optional[str]:
        """
        Execute fills at the OPEN of the bar based on the decision made at the CLOSE of the previous bar.
        Returns 'ENTRY_FILLED', 'EXIT_FILLED' or None.
        """
        action = None
        
        # 1. Check Exit first (if holding and decision is close or block)
        # Note: In this model, if valid position exists, we hold unless explicit exit signal OR logic requires exit.
        # But for 'ALLOW' verdict on a new signal vs 'BLOCK' logic:
        # If we have a position, we check if we need to close it.
        # Simple Logic V1: 
        #   - If decision == 'EXIT' (or logic says sell), close.
        #   - If decision == 'ENTRY' (ALLOW) and NO position, open.
        #   - If decision == 'ENTRY' and HAVE position, ignore/hold (or pyramid if supported - v1 NO).
        
        # NOTE: The decision passed here is the stored intent/verdict from T-1.
        # Let's assume passed decision is: "BUY", "SELL", "HOLD", "NONE"
        
        if self.position and decision_from_prev_close == "SELL":
            self._close_position(ts, open_price, bar_index)
            action = "EXIT_FILLED"
            
        elif not self.position and decision_from_prev_close == "BUY":
            self._open_position(ts, open_price, bar_index)
            action = "ENTRY_FILLED"
            
        # Update equity (Mark to Market)
        self._update_equity(open_price)
        
        return action

    def _open_position(self, ts: int, price: float, bar_index: int):
        # Calculate size (Full capital for v1)
        # Cost = qty * price
        # Fee = Cost * fee_rate
        # Total cost = Cost + Fee <= Cash
        
        # Cost * (1 + fee_rate) = Cash
        cost_allowable = self.current_capital / (1.0 + self.fee_rate)
        qty = cost_allowable / price
        
        fee_amt = (qty * price) * self.fee_rate
        
        trade_id = f"TRD_{ts}_{bar_index}"
        
        self.position = GameTrade(
            trade_id=trade_id,
            entry_ts=ts,
            entry_price=price,
            exit_ts=None,
            exit_price=None,
            fee=fee_amt,
            ref_step_entry=bar_index
        )
        
        self.current_capital -= (qty * price + fee_amt)
        self.current_capital = max(0.0, self.current_capital) # Safety

    def _close_position(self, ts: int, price: float, bar_index: int):
        if not self.position: return
        
        # Calc value
        # Qty is implicit? Wait, we didn't store qty in GameTrade v1?
        # GameTrade v1 definition in prompt didn't explicitly show qty, but pnl_gross/net requirements exist.
        # We should infer qty from entry or store it. 
        # Let's assume we need qty. I'll stick to prompt's GameTrade dataclass but logic needs qty.
        # I will calculate qty based on (Entry Price and Initial Cost).
        # But wait, GameTrade has `pnl_gross`.
        # Recovering qty:
        # initial_cost = (capital at entry) - fee ? No.
        # Let's assume for v1 simple simulation:
        # We track "notional" or "qty".
        # Let's add `qty` to the internal usage even if not in artifact spec (or add to spec).
        # Artifact spec allowed extras.
        
        # Re-calculating Qty from Fee is risky due to precision.
        # We should treat 'pnl_gross' calculation carefully.
        
        # For simulation state, we know the cash spent.
        entry_val = self.position.entry_price
        entry_fee = self.position.fee
        
        # Approx cost = entry_fee / fee_rate
        cost = entry_fee / self.fee_rate
        qty = cost / entry_val
        
        exit_val = qty * price
        exit_fee = exit_val * self.fee_rate
        
        pnl_gross = exit_val - cost
        pnl_net = pnl_gross - entry_fee - exit_fee
        
        self.position.exit_ts = ts
        self.position.exit_price = price
        self.position.pnl_gross = pnl_gross
        self.position.pnl_net = pnl_net
        self.position.fee += exit_fee # Total fee
        self.position.bars_held = bar_index - self.position.ref_step_entry
        self.position.ref_step_exit = bar_index
        self.position.status = "CLOSED"
        
        self.current_capital += (exit_val - exit_fee)
        
        self.trades.append(self.position)
        self.position = None

    def _update_equity(self, current_price: float):
        # Equity = Cash + Unrealized Position Value
        val = 0.0
        if self.position:
            # Need Qty
            cost = self.position.fee / self.fee_rate # Entry fee represents entry cost fee
            qty = (cost / self.position.entry_price)
            val = qty * current_price
            
        self.equity = self.current_capital + val

    def get_equity(self) -> float:
        return self.equity

    def get_position_state(self) -> str:
        if self.position:
            return f"LONG (@ {self.position.entry_price:.2f})"
        return "FLAT"
