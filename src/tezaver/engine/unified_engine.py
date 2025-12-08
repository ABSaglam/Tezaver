"""
Tezaver Unified Engine Orchestrator (M25)
=========================================

This class is the conductor of the orchestra. 
It connects the Analyzer, Strategist, and Executor.
It does NOT contain logic itself; it only passes data.
"""

from typing import List, Dict, Any
from .interfaces import IAnalyzer, IStrategist, IExecutor, MarketSignal, TradeDecision

class UnifiedEngine:
    def __init__(self, analyzer: IAnalyzer, strategist: IStrategist, executor: IExecutor):
        self.analyzer = analyzer
        self.strategist = strategist
        self.executor = executor
        
    def tick(self, symbol: str, timeframe: str, market_data: Any) -> Dict[str, Any]:
        """
        Process a single 'tick' or data update for a symbol.
        """
        result = {
            "symbol": symbol,
            "timestamp": None,
            "signals": [],
            "decision": None,
            "execution": None
        }
        
        # 1. ANALYZE
        signals = self.analyzer.analyze(symbol, timeframe, market_data)
        
        # Get current account state from Executor (Early access needed for Position Monitoring)
        account_state = self.executor.get_balance()
        
        # --- POSITION MONITORING INJECTION ---
        # If we have no signals, but we HOLD a position, we must still wake up the Strategist
        # to check for Stop Loss / Take Profit.
        if not signals:
            positions = account_state.get("positions", {})
            my_pos = positions.get(symbol)
            if my_pos and my_pos.get('qty', 0) > 0:
                # Create a synthetic MONITOR signal
                try:
                    last_bar = market_data.iloc[-1]
                    current_price = float(last_bar['close'])
                    current_time = last_bar.name # Index is datetime
                    
                    montior_signal = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "signal_type": "MONITOR",
                        "timestamp": current_time,
                        "score": 0.0,
                        "metadata": {"current_price": current_price, "close": current_price}
                    }
                    signals = [montior_signal]
                except Exception:
                    # If market_data structure is unknown/different, skip monitoring
                    pass

        result["signals"] = signals
        
        if not signals:
            return result
            
        # 2. DECIDE (Strategy)
        # We process signals. If multiple, strategy decides priority.
        
        decision = None
        for signal in signals:
            decision = self.strategist.evaluate(signal, account_state)
            if decision:
                break # Act on first valid decision for now
        
        result["decision"] = decision
        
        if not decision:
            return result
            
        # 3. EXECUTE
        execution_report = self.executor.execute(decision)
        result["execution"] = execution_report
        
        return result
