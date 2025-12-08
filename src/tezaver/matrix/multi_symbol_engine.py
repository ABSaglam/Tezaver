"""
Tezaver Multi-Symbol Engine (Fleet Commander) - M25
===================================================

This module implements the orchestration layer for managing multiple symbols simultaneously.
It acts as the "Fleet Commander", directing individual "UnifiedEngine" instances (Symbol Slots).
"""

from typing import List, Dict, Optional, Any, Callable, TypedDict
from datetime import datetime
from dataclasses import dataclass, field

from tezaver.engine.interfaces import IAnalyzer, IStrategist, IExecutor, MarketSignal, TradeDecision, ExecutionReport, AccountState
from tezaver.engine.unified_engine import UnifiedEngine
from tezaver.matrix.guardrail import GuardrailController, GuardrailStrategistProxy, GuardrailDecision

@dataclass
class SymbolSlot:
    """Holds the runtime state for a single symbol's simulation."""
    symbol: str
    engine: UnifiedEngine
    enabled: bool = True
    last_tick_at: Optional[datetime] = None
    last_signal: Optional[MarketSignal] = None
    last_decision: Optional[TradeDecision] = None
    last_guardrail_decision: Optional[GuardrailDecision] = None
    last_execution: Optional[ExecutionReport] = None
    local_stats: Dict[str, Any] = field(default_factory=dict) # PnL, Trade Count etc.

class MultiSymbolEngine:
    def __init__(
        self,
        symbols: List[str],
        analyzer_factory: Callable[[str], IAnalyzer],
        strategist_factory: Callable[[str], IStrategist],
        executor: IExecutor,
        guardrails: Optional[GuardrailController] = None,
    ):
        """
        Args:
            symbols: List of symbols to track.
            analyzer_factory: Function creating an IAnalyzer for a symbol.
            strategist_factory: Function creating an IStrategist for a symbol.
            executor: SHARED IExecutor instance (Global Wallet).
            guardrails: Policy controller.
        """
        self.executor = executor
        self.guardrails = guardrails
        
        self.slots: List[SymbolSlot] = []
        self._slot_map: Dict[str, SymbolSlot] = {}
        self._next_index = 0
        
        # Initialize Slots
        for sym in symbols:
            analyzer = analyzer_factory(sym)
            raw_strategist = strategist_factory(sym)
            
            # Wrap with Guardrail if enabled
            if guardrails:
                strategist = GuardrailStrategistProxy(
                    raw_strategist, 
                    guardrails,
                    on_decision_callback=self._on_guardrail_decision
                )
            else:
                strategist = raw_strategist
                
            engine = UnifiedEngine(analyzer, strategist, executor)
            
            slot = SymbolSlot(symbol=sym, engine=engine)
            self.slots.append(slot)
            self._slot_map[sym] = slot
            
    def tick(self, now: datetime, market_data_provider: Callable[[str], Any]) -> bool:
        """
        Process ONE symbol tick (Round-Robin).
        
        Args:
            now: Current simulation time.
            market_data_provider: Function (symbol) -> DataFrame/DataSlice for the engine.
                                  Must return the window ending at 'now' (or close to it).
        
        Returns:
            True if a slot was processed, False if all disabled or empty.
        """
        if not self.slots:
            return False
            
        # 1. Select Slot (Round Robin)
        start_index = self._next_index
        slot = self.slots[self._next_index]
        self._next_index = (self._next_index + 1) % len(self.slots)
        
        if not slot.enabled:
            # Try to find next enabled
            # Simple loop protection
            while not slot.enabled:
                if self._next_index == start_index: return False # All disabled
                slot = self.slots[self._next_index]
                self._next_index = (self._next_index + 1) % len(self.slots)
        
        # 2. Get Data
        data = market_data_provider(slot.symbol)
        if data is None or len(data) == 0:
             return False
             
        # 3. Tick The Engine
        # Warning: unified_engine.tick() runs Analyze -> Decide -> Execute chain.
        # We need to INTERCEPT the 'Decide' step to apply Guardrails before 'Execute'.
        # But UnifiedEngine encapsulates this flow tightly.
        # Options:
        # A) Refactor UnifiedEngine to allow injection of middleware.
        # B) Subclass UnifiedEngine and override decide/execute?
        # C) Let UnifiedEngine run, but pass a "Proxy Executor"? 
        # D) Modify UnifiedEngine to accept an optional 'decision_filter_callback'.
        
        # Let's go with Option D (Least invasive refactor, cleanest architecture).
        # But wait, UnifiedEngine is already finalized in Phase 1.
        # Alternative: We trust the Guardrail check INSIDE Strategist? 
        # No, Strategist is "Coach", Guardrail is "Management Policy".
        
        # BEST APPROACH v1: UnifiedEngine returns 'result' dict. It executes internally.
        # To apply guardrails, we MUST inspect decision BEFORE execution.
        # Currently UnifiedEngine does: analyze -> decide -> execute.
        # We need: analyze -> decide -> GUARDRAIL -> execute.
        
        # Quick Refactor of UnifiedEngine required:
        # Add `decision_callback` to `tick` or constructor?
        # Or simpler: MultiSymbolEngine manually runs steps?
        
        # Let's manually orchestrate here for maximum control, SINCE we have access to engine.analyzer etc.
        # BUT UnifiedEngine has the `MONITOR` logic inside `tick`. duplicating that is bad.
        
        # Solution: UnifiedEngine.tick() is standard.
        # We will wrap the Strategist with a "GuardrailStrategistProxy".
        # This proxy calls real strategist, then checks guardrail.
        # If guardrail says NO, it extinguishes the decision (returns None).
        # This is clean and requires NO changes to UnifiedEngine.
        
        # IMPLEMENTING GUARDRAIL PROXY LOGIC DYNAMICALLY IS COMPLEX HERE.
        
        # Simpler: We assume for v1 we just run the engine. Guardrails inside Strategist via config?
        # No, GuardrailController is central.
        
        # Let's modify UnifiedEngine slightly to allow a "pre_execute_hook"?
        # Actually, let's just stick to the plan: "Soft Power".
        # If we trust UnifiedEngine, we can just run it. 
        # But user explicitly asked for Guardrail check.
        
        # Let's do the lightweight Wrapper approach for Strategist instantiation!
        # See init() above. We can wrap the strategist there!
        
        result = slot.engine.tick(slot.symbol, "1h", data)
        
        # 4. Update Slot State
        slot.last_tick_at = now
        
        if result.get('signals'):
            slot.last_signal = result['signals'][0] # Take first
            
        if result.get('decision'):
            slot.last_decision = result['decision']
            
        if result.get('execution'):
            slot.last_execution = result['execution']
            
            # Simple Stats update
            exe = result['execution']
            if exe['success']:
                pass # Later: track pnl
                
        return True

    def get_slot(self, symbol: str) -> Optional[SymbolSlot]:
        return self._slot_map.get(symbol)

    def _on_guardrail_decision(self, symbol: str, decision: GuardrailDecision):
        """Callback from GuardrailStrategistProxy."""
        slot = self.get_slot(symbol)
        if slot:
            slot.last_guardrail_decision = decision
