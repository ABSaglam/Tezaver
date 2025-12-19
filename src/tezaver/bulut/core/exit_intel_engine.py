# Tezaver Bulut - Exit Intel Engine (P8)
"""
Pattern-aware exit intelligence engine.
Computes optimal SL/TP levels based on:
- Exit profiles (v2 rules)
- ATR/volatility data
- Pattern confidence
- Position state
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from tezaver.bulut.schemas.exit_profile_v2 import (
    ExitProfileV2, ComputedExitLevels, ExitRule,
    FixedPctRule, AtrStopRule, TrailingStopRule, BreakEvenRule, TimeStopRule,
    parse_exit_rule
)


@dataclass
class ExitDecision:
    """Record of an exit level computation."""
    position_id: str
    symbol: str
    computed_sl: Optional[float]
    computed_tp: Optional[float]
    profile_id: str
    rule_type: str
    reason: str
    timestamp: str


class ExitIntelEngine:
    """
    Exit Intelligence Engine for pattern-aware exits.
    
    Precedence:
    1. Symbol + Pattern override
    2. Pattern only
    3. Symbol only  
    4. Global default
    """
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._profiles: Dict[str, ExitProfileV2] = {}
        self._decisions: List[ExitDecision] = []
        self._load_profiles()
    
    def _load_profiles(self):
        """Load exit profiles from persistence/config."""
        # Default global profile - always provides SL/TP
        self._profiles["global_default"] = ExitProfileV2(
            profile_id="global_default",
            name="Global Default",
            rules=[
                {"type": "fixed_pct", "sl_pct": 2.0, "tp_pct": 4.0},
                {"type": "time_stop", "max_hold_hours": 72}
            ],
            priority=1  # Higher priority for guaranteed SL/TP
        )
        
        # ATR-based global (only selected when specifically matched)
        self._profiles["global_atr"] = ExitProfileV2(
            profile_id="global_atr",
            name="Global ATR",
            rules=[
                {"type": "atr_stop", "sl_atr_mult": 1.5, "tp_atr_mult": 3.0, "atr_tf": "1h"},
                {"type": "fixed_pct", "sl_pct": 2.0, "tp_pct": 4.0},  # Fallback if no ATR
                {"type": "time_stop", "max_hold_hours": 48}
            ],
            priority=0  # Lower priority, opt-in via custom profiles
        )
        
        # Load custom profiles from persistence
        try:
            custom = self._ctx.persistence.get_exit_profiles()
            for p in (custom or []):
                profile = ExitProfileV2(
                    profile_id=p.get("profile_id", ""),
                    name=p.get("name", ""),
                    rules=p.get("rules", []),
                    priority=p.get("priority", 0),
                    symbol=p.get("symbol"),
                    pattern_id=p.get("pattern_id"),
                    confidence_min=p.get("confidence_min")
                )
                self._profiles[profile.profile_id] = profile
        except Exception:
            pass
    
    def resolve_profile(
        self, 
        symbol: str, 
        pattern_id: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> ExitProfileV2:
        """
        Resolve the best exit profile for given context.
        
        Precedence: Symbol+Pattern > Pattern > Symbol > Global
        """
        candidates = []
        
        for profile in self._profiles.values():
            if not profile.enabled:
                continue
            
            # Check confidence requirement
            if profile.confidence_min and confidence and confidence < profile.confidence_min:
                continue
            
            # Match criteria
            matches_symbol = profile.symbol is None or profile.symbol == symbol
            matches_pattern = profile.pattern_id is None or profile.pattern_id == pattern_id
            
            if matches_symbol and matches_pattern:
                # Calculate match specificity
                specificity = 0
                if profile.symbol == symbol:
                    specificity += 10
                if profile.pattern_id == pattern_id:
                    specificity += 10
                
                candidates.append((profile, profile.priority + specificity))
        
        if not candidates:
            return self._profiles["global_default"]
        
        # Sort by priority (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def compute_exit_levels(
        self,
        position: Dict[str, Any],
        current_price: Optional[float] = None,
        atr_value: Optional[float] = None
    ) -> ComputedExitLevels:
        """
        Compute exit levels for a position.
        
        Args:
            position: Position dict with symbol, entry_price, side, pattern_id, etc.
            current_price: Current market price
            atr_value: ATR value for ATR-based stops
        
        Returns:
            ComputedExitLevels with sl_price, tp_price, etc.
        """
        symbol = position.get("symbol", "")
        entry_price = position.get("entry_price", 0.0)
        side = position.get("side", "LONG")  # LONG or SHORT
        pattern_id = position.get("pattern_id")
        confidence = position.get("pattern_confidence")
        open_ts = position.get("open_ts")
        
        is_long = side.upper() == "LONG"
        
        # Resolve profile
        profile = self.resolve_profile(symbol, pattern_id, confidence)
        
        levels = ComputedExitLevels(
            profile_id=profile.profile_id,
            rule_source=profile.name
        )
        
        # Process rules in order
        for rule_dict in profile.rules:
            rule = parse_exit_rule(rule_dict)
            if not rule or not getattr(rule, 'enabled', True):
                continue
            
            if isinstance(rule, FixedPctRule):
                self._apply_fixed_pct(levels, entry_price, rule, is_long)
            elif isinstance(rule, AtrStopRule):
                self._apply_atr_stop(levels, entry_price, rule, is_long, atr_value)
            elif isinstance(rule, TrailingStopRule):
                self._apply_trailing_stop(levels, entry_price, current_price, rule, is_long)
            elif isinstance(rule, BreakEvenRule):
                self._apply_break_even(levels, entry_price, current_price, rule, is_long)
            elif isinstance(rule, TimeStopRule):
                self._apply_time_stop(levels, open_ts, rule)
        
        # Record decision
        decision = ExitDecision(
            position_id=position.get("position_id", ""),
            symbol=symbol,
            computed_sl=levels.sl_price,
            computed_tp=levels.tp_price,
            profile_id=profile.profile_id,
            rule_type=self._get_primary_rule_type(profile),
            reason=f"Profile: {profile.name}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self._decisions.append(decision)
        if len(self._decisions) > 500:
            self._decisions = self._decisions[-250:]
        
        return levels
    
    def _apply_fixed_pct(
        self, 
        levels: ComputedExitLevels, 
        entry: float, 
        rule: FixedPctRule,
        is_long: bool
    ):
        """Apply fixed percentage SL/TP."""
        if levels.sl_price is None:
            if is_long:
                levels.sl_price = entry * (1 - rule.sl_pct / 100)
            else:
                levels.sl_price = entry * (1 + rule.sl_pct / 100)
        
        if levels.tp_price is None:
            if is_long:
                levels.tp_price = entry * (1 + rule.tp_pct / 100)
            else:
                levels.tp_price = entry * (1 - rule.tp_pct / 100)
    
    def _apply_atr_stop(
        self,
        levels: ComputedExitLevels,
        entry: float,
        rule: AtrStopRule,
        is_long: bool,
        atr_value: Optional[float]
    ):
        """Apply ATR-based SL/TP."""
        if atr_value is None or atr_value <= 0:
            return  # Can't compute without ATR
        
        if levels.sl_price is None:
            sl_distance = atr_value * rule.sl_atr_mult
            if is_long:
                levels.sl_price = entry - sl_distance
            else:
                levels.sl_price = entry + sl_distance
        
        if levels.tp_price is None:
            tp_distance = atr_value * rule.tp_atr_mult
            if is_long:
                levels.tp_price = entry + tp_distance
            else:
                levels.tp_price = entry - tp_distance
    
    def _apply_trailing_stop(
        self,
        levels: ComputedExitLevels,
        entry: float,
        current_price: Optional[float],
        rule: TrailingStopRule,
        is_long: bool
    ):
        """Apply trailing stop logic."""
        if current_price is None:
            return
        
        pnl_pct = ((current_price - entry) / entry) * 100 if is_long else ((entry - current_price) / entry) * 100
        
        if pnl_pct >= rule.activation_pct:
            levels.trailing_active = True
            trail_distance = current_price * (rule.trail_pct / 100)
            
            if is_long:
                new_trail_sl = current_price - trail_distance
                # Only move up, never down
                if levels.trailing_sl is None or new_trail_sl > levels.trailing_sl:
                    levels.trailing_sl = new_trail_sl
            else:
                new_trail_sl = current_price + trail_distance
                if levels.trailing_sl is None or new_trail_sl < levels.trailing_sl:
                    levels.trailing_sl = new_trail_sl
    
    def _apply_break_even(
        self,
        levels: ComputedExitLevels,
        entry: float,
        current_price: Optional[float],
        rule: BreakEvenRule,
        is_long: bool
    ):
        """Apply break-even stop logic."""
        if current_price is None:
            return
        
        pnl_pct = ((current_price - entry) / entry) * 100 if is_long else ((entry - current_price) / entry) * 100
        
        if pnl_pct >= rule.at_profit_pct and rule.move_sl_to_entry:
            levels.break_even_triggered = True
            buffer = entry * (rule.buffer_pct / 100)
            
            if is_long:
                be_sl = entry + buffer
                if levels.sl_price is None or be_sl > levels.sl_price:
                    levels.sl_price = be_sl
            else:
                be_sl = entry - buffer
                if levels.sl_price is None or be_sl < levels.sl_price:
                    levels.sl_price = be_sl
    
    def _apply_time_stop(
        self,
        levels: ComputedExitLevels,
        open_ts: Optional[str],
        rule: TimeStopRule
    ):
        """Apply time-based exit."""
        if open_ts is None:
            return
        
        try:
            open_dt = datetime.fromisoformat(open_ts.replace("Z", "+00:00"))
            expire_dt = open_dt + timedelta(hours=rule.max_hold_hours)
            levels.time_stop_due = expire_dt.isoformat()
        except Exception:
            pass
    
    def _get_primary_rule_type(self, profile: ExitProfileV2) -> str:
        """Get the primary rule type from profile."""
        if profile.rules:
            return profile.rules[0].get("type", "unknown")
        return "unknown"
    
    def get_status(self) -> Dict[str, Any]:
        """Get exit intel engine status."""
        return {
            "profiles_loaded": len(self._profiles),
            "profile_ids": list(self._profiles.keys()),
            "decisions_count": len(self._decisions)
        }
    
    def get_decisions(self, limit: int = 50) -> List[Dict]:
        """Get recent exit decisions."""
        decisions = self._decisions[-limit:]
        return [
            {
                "position_id": d.position_id,
                "symbol": d.symbol,
                "computed_sl": d.computed_sl,
                "computed_tp": d.computed_tp,
                "profile_id": d.profile_id,
                "rule_type": d.rule_type,
                "reason": d.reason,
                "timestamp": d.timestamp
            }
            for d in reversed(decisions)
        ]
    
    def preview_exit(
        self,
        symbol: str,
        entry_price: float,
        side: str = "LONG",
        pattern_id: Optional[str] = None,
        current_price: Optional[float] = None,
        atr_value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Preview exit levels without a real position.
        
        Useful for UI previews.
        """
        position = {
            "position_id": "preview",
            "symbol": symbol,
            "entry_price": entry_price,
            "side": side,
            "pattern_id": pattern_id,
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        levels = self.compute_exit_levels(position, current_price, atr_value)
        profile = self.resolve_profile(symbol, pattern_id)
        
        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "side": side,
            "sl_price": levels.sl_price,
            "tp_price": levels.tp_price,
            "trailing_active": levels.trailing_active,
            "trailing_sl": levels.trailing_sl,
            "break_even_triggered": levels.break_even_triggered,
            "time_stop_due": levels.time_stop_due,
            "profile_id": profile.profile_id,
            "profile_name": profile.name,
            "rules_summary": [r.get("type") for r in profile.rules]
        }
