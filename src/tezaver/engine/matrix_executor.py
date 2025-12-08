"""
Tezaver Matrix Executor (Simulated Exchange)
============================================

This module implements the IExecutor interface for the "Matrix Mode" (Simulation/Paper Trading).
It acts as a virtual exchange, tracking balance and processing orders locally.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from .interfaces import IExecutor, TradeDecision, ExecutionReport, AccountState, Position

class MatrixExecutor: # Implements IExecutor
    def __init__(self, initial_balance_usdt: float = 10000.0, commission_rate: float = 0.001):
        """
        Args:
            initial_balance_usdt: Starting paper money.
            commission_rate: Trading fee per order (default 0.1% for Binance Spot).
        """
        self.balance: Dict[str, float] = {"USDT": initial_balance_usdt}
        # Positions: {symbol: Position}
        self.positions: Dict[str, Position] = {}
        self.commission_rate = commission_rate
        self.trade_history: List[ExecutionReport] = []
        
    def get_balance(self) -> AccountState:
        """
        Return the standardized account state.
        This includes Equity (Total Value) and Positions.
        """
        cash = self.balance.get("USDT", 0.0)
        
        # Calculate Equity
        # For simplicity in Sim, we assume current price = avg price or last known.
        # Ideally, we should receive current prices to calc equity, but IExecutor.get_balance signature 
        # is parameterless by design (Snapshot).
        # We will update unrealized PnL during tick loops if needed, or assume mark-to-market.
        # For now, Equity = Cash + (Qty * Avg Price) approximation
        
        equity = cash
        for pos in self.positions.values():
            equity += pos['qty'] * pos['avg_price'] # Using Cost Basis for now if price unknown
            
        return {
            "equity": equity,
            "available_cash": cash,
            "positions": self.positions.copy()
        }
    
    # Helper for legacy calls if any
    def get_portfolio_value_usdt(self, current_prices: Dict[str, float]) -> float:
        total = self.balance.get("USDT", 0.0)
        for symbol, pos in self.positions.items():
             price = current_prices.get(symbol, pos['avg_price'])
             total += pos['qty'] * price
        return total
        
    def execute(self, decision: TradeDecision) -> ExecutionReport:
        """
        Execute a trade decision in the virtual exchange.
        """
        order_id = f"sim_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now()
        
        symbol = decision['symbol']
        action = decision['action']
        qty = decision['quantity']
        price = decision['price'] if decision['price'] else 0.0 # Market order sim needs price
        
        # 1. VALIDATION
        if action == "NONE":
             return _create_report(False, "SKIPPED", order_id, symbol, action, 0, 0, 0, timestamp, "No Action")
             
        if action == "BUY":
            cost = qty * price
            fee = cost * self.commission_rate
            total_cost = cost + fee
            
            if self.balance.get("USDT", 0) < total_cost:
                return _create_report(False, "REJECTED", order_id, symbol, action, 0, 0, 0, timestamp, "Insufficient Funds")
                
            # EXECUTE BUY
            self.balance["USDT"] -= total_cost
            
            # Position Management (Weighted Avg)
            current_pos = self.positions.get(symbol)
            if current_pos:
                old_qty = current_pos['qty']
                old_cost = old_qty * current_pos['avg_price']
                new_cost = qty * price
                total_qty = old_qty + qty
                avg_price = (old_cost + new_cost) / total_qty
            else:
                total_qty = qty
                avg_price = price
                
            self.positions[symbol] = {
                "symbol": symbol,
                "qty": total_qty,
                "avg_price": avg_price,
                "unrealized_pnl": 0.0 # Reset/Recalc later
            }
            
            self._log_trade(True, "FILLED", order_id, symbol, action, qty, price, fee, timestamp, None)
            return _create_report(True, "FILLED", order_id, symbol, action, qty, price, fee, timestamp, None)
            
        elif action == "SELL":
            current_pos = self.positions.get(symbol)
            if not current_pos or current_pos['qty'] < qty:
                return _create_report(False, "REJECTED", order_id, symbol, action, 0, 0, 0, timestamp, "Insufficient Position")
                
            # EXECUTE SELL
            revenue = qty * price
            fee = revenue * self.commission_rate
            net_revenue = revenue - fee
            
            self.balance["USDT"] += net_revenue
            
            # Reduce Position
            new_qty = current_pos['qty'] - qty
            if new_qty <= 1e-9:
                del self.positions[symbol]
            else:
                self.positions[symbol]['qty'] = new_qty
                
            self._log_trade(True, "FILLED", order_id, symbol, action, qty, price, fee, timestamp, None)
            return _create_report(True, "FILLED", order_id, symbol, action, qty, price, fee, timestamp, None)
            
        return _create_report(False, "FAILED", order_id, symbol, action, 0, 0, 0, timestamp, "Unknown Action")

    def _log_trade(self, success, status, order_id, symbol, action, qty, price, fee, timestamp, error):
        report = _create_report(success, status, order_id, symbol, action, qty, price, fee, timestamp, error)
        self.trade_history.append(report)

def _create_report(success, status, order_id, symbol, action, qty, price, fee, timestamp, error) -> ExecutionReport:
    return {
        "success": success,
        "status": status,
        "order_id": order_id,
        "symbol": symbol,
        "action": action,
        "filled_qty": qty,
        "filled_price": price,
        "commission": fee,
        "timestamp": timestamp,
        "error_message": error
    }
