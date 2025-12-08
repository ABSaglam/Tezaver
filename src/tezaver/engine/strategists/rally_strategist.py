"""
Tezaver Rally Strategist (The Coach) - M25
==========================================

This module implements the IStrategist interface.
It receives Rally signals and decides whether to enter a trade.
It manages risk (Position Sizing, Stop Loss, Take Profit).
"""

from typing import Optional, Dict, Any
from tezaver.engine.interfaces import IStrategist, MarketSignal, TradeDecision, AccountState

class RallyStrategist(IStrategist):
    def __init__(self, risk_per_trade_pct: float = 0.10, stop_loss_pct: float = 0.05, take_profit_pct: float = 0.15):
        """
        Args:
            risk_per_trade_pct: How much of the TOTAL balance to put into one trade (e.g., 0.10 = 10%).
            stop_loss_pct: Stop loss percentage (e.g. 0.05 = 5% below entry).
            take_profit_pct: Take profit percentage.
        """
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
    def evaluate(self, signal: MarketSignal, account_state: AccountState) -> Optional[TradeDecision]:
        """
        Evaluate and decide:
        - If we hold position: Check Exit (TP/SL)
        - If we don't hold: Check Entry (Signal)
        """
        symbol = signal['symbol']
        metadata = signal.get("metadata", {})
        current_price = metadata.get("current_price") or metadata.get("close")
        if not current_price:
             # Fallback to score if metadata invalid (unlikely)
             return None

        # --- 1. EXIT LOGIC (CHECK HOLDINGS) ---
        positions = account_state.get("positions", {})
        my_pos = positions.get(symbol)
        
        if my_pos and my_pos['qty'] > 0:
            # We have a position, check for TP/SL
            entry_price = my_pos['avg_price']
            qty = my_pos['qty']
            
            # PnL Calculation
            pnl_pct = (current_price - entry_price) / entry_price
            
            reason = ""
            should_sell = False
            
            # Take Profit (e.g. +15%)
            if pnl_pct >= self.take_profit_pct:
                should_sell = True
                reason = f"Take Profit Triggered (+{pnl_pct*100:.1f}%)"
            
            # Stop Loss (e.g. -5%)
            elif pnl_pct <= -self.stop_loss_pct:
                should_sell = True
                reason = f"Stop Loss Triggered ({pnl_pct*100:.1f}%)"
                
            if should_sell:
                return {
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": qty, # Sell All
                    "price": current_price,
                    "stop_loss": None,
                    "take_profit": None,
                    "reason": reason
                }
            else:
                return None # HOLD
        
        # --- 2. ENTRY LOGIC (CHECK SIGNALS) ---
        
        if signal['signal_type'] != "RALLY_START":
            return None
        
        if signal['score'] < 50: # Minimum score filter
            return None

        # Check Funds
        available_cash = account_state.get("available_cash", 0.0)
        
        # Fallback for old style dicts if not strictly typed yet
        if available_cash == 0.0 and "USDT" in account_state: # type: ignore
             available_cash = account_state["USDT"] # type: ignore
             
        if available_cash < 10: return None
            
        # Position Sizing
        amount_to_invest = available_cash * self.risk_per_trade_pct
        if amount_to_invest < 10: amount_to_invest = available_cash
            
        quantity = amount_to_invest / current_price
        
        return {
            "action": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": current_price,
            "stop_loss": current_price * (1 - self.stop_loss_pct),
            "take_profit": current_price * (1 + self.take_profit_pct),
            "reason": f"Rally Start (Score: {signal['score']:.2f})"
        }
