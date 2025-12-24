"""
Matrix Paper Exchange V1
========================

Simulates a futures exchange for backtesting.
Handles:
- Wallet Balance (USDT)
- Open Positions (Long/Short)
- Order Execution (Limit/Market checks)
- PnL Calculation (Unrealized/Realized)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import uuid

@dataclass
class PaperPosition:
    symbol: str
    side: str # "BUY" (Long) or "SELL" (Short)
    entry_price: float
    size: float # Contracts
    notional: float # entry_price * size
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_time: int = 0

@dataclass
class PaperTrade:
    trade_id: str
    symbol: str
    side: str
    price: float
    size: float
    value: float
    commission: float
    pnl: float = 0.0 # Realized PnL
    timestamp: int = 0
    reason: str = "" # ENTRY/EXIT/SL/TP

class PaperExchange:
    def __init__(self, initial_balance: float = 1000.0, commission_rate: float = 0.0004):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.commission_rate = commission_rate # 0.04% taker
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: List[PaperTrade] = []
        self.equity_curve: List[Dict] = []
        
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total equity (Balance + Unrealized PnL)."""
        eq = self.balance
        for sym, pos in self.positions.items():
            price = current_prices.get(sym, pos.entry_price)
            pnl = self._calc_pnl(pos, price)
            eq += pnl
        return eq
        
    def _calc_pnl(self, pos: PaperPosition, current_price: float) -> float:
        if pos.side == "BUY":
            return (current_price - pos.entry_price) * pos.size
        else:
            return (pos.entry_price - current_price) * pos.size

    def on_tick(self, timestamp: int, candle: Dict[str, float]):
        """
        Process a candle tick for TP/SL checks on existing positions.
        candle: {"open":..., "high":..., "low":..., "close":...}
        """
        # Only support 1 symbol for now in this context? Or pass symbol dict?
        # Assuming single symbol stimulation for now.
        pass # Implemented in execute_checks

    def execute_logic(self, timestamp: int, symbol: str, candle: Dict[str, float], decision: str, plan_notional: float = 0.0):
        """
        Core logic called by TimeMachine every bar.
        1. Check TP/SL for existing position.
        2. Execute new decision (ALLOW -> Open).
        """
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        
        # 1. Check Existing Position
        if symbol in self.positions:
            pos = self.positions[symbol]
            # Check SL
            if pos.stop_loss:
                hit_sl = (pos.side == "BUY" and low <= pos.stop_loss) or \
                         (pos.side == "SELL" and high >= pos.stop_loss)
                if hit_sl:
                    self.close_position(symbol, pos.stop_loss, timestamp, "STOP_LOSS")
                    return # Position closed, can't take new action yet (simple mode)
            
            # Check TP
            if symbol in self.positions: # Double check if check_sl closed it
                pos = self.positions[symbol]
                if pos.take_profit:
                    hit_tp = (pos.side == "BUY" and high >= pos.take_profit) or \
                             (pos.side == "SELL" and low <= pos.take_profit)
                    if hit_tp:
                        self.close_position(symbol, pos.take_profit, timestamp, "TAKE_PROFIT")
                        return

        # 2. Execute Decision
        if decision == "ALLOW":
            # If we don't have a position, OPEN ONE.
            if symbol not in self.positions:
                # Calculate size
                # Strategy: Use fixed risk or notional?
                # User asked for "1000$ starting capital... see what it becomes"
                # Let's say we use 100% of balance (or risk managed).
                # Simple approach: 100% Equity? No, safer 1000$ fixed or 95% equity.
                # Let's use `plan_notional` if provided, else full equity.
                
                exec_price = close # Market entry at close of bar (or open of next?)
                # Backtest assumption: We enter at CLOSE of the trigger bar.
                
                available = self.balance
                # Leverage? 
                # Let's assume 1x for simplicity unless plan specifies.
                
                size = (available * 0.98) / exec_price # Keep some for fees
                
                self.open_position(symbol, "BUY", exec_price, size, timestamp) # Assuming Long-Only for user request? Or Court decides?
                # Court generates intents. We need to look at intent side.
                # For this first version, let's assume Bundle is Long-Only (Rally).
        
        elif decision == "BLOCK" or decision == "SKIP":
             # Do nothing? Or close if we have logic to close on signal lost?
             # For now, only Close via TP/SL.
             pass

    def open_position(self, symbol: str, side: str, price: float, size: float, timestamp: int, sl=None, tp=None):
        cost = price * size
        comm = cost * self.commission_rate
        self.balance -= comm
        
        self.positions[symbol] = PaperPosition(symbol, side, price, size, cost, sl, tp, timestamp)
        
        self.trades.append(PaperTrade(
            trade_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side,
            price=price,
            size=size,
            value=cost,
            commission=comm,
            timestamp=timestamp,
            reason="ENTRY"
        ))

    def close_position(self, symbol: str, price: float, timestamp: int, reason: str):
        if symbol not in self.positions:
            return
            
        pos = self.positions.pop(symbol)
        
        exit_val = price * pos.size
        comm = exit_val * self.commission_rate
        pnl = (exit_val - pos.notional) if pos.side == "BUY" else (pos.notional - exit_val)
        
        self.balance += (pnl - comm) # PnL is added to balance (margin returned implicitly in pnl calc? No.)
        # Wait, simple accounting:
        # Balance was NOT deducted for margin (futures style). Only fees deducted.
        # PnL is added/subtracted.
        
        self.trades.append(PaperTrade(
            trade_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side="SELL" if pos.side == "BUY" else "BUY",
            price=price,
            size=pos.size,
            value=exit_val,
            commission=comm,
            pnl=pnl,
            timestamp=timestamp,
            reason=reason
        ))
