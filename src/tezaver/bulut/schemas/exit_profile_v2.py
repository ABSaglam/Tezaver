# Tezaver Bulut - Exit Profile v2 Schema (P8)
"""
Exit profile schemas with expanded rule types:
- fixed_pct: Fixed percentage SL/TP
- atr_stop: ATR-based dynamic SL/TP
- trailing_stop: Activation + trailing distance
- break_even: Move SL to entry at profit threshold
- time_stop: Close after time window
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum


class ExitRuleType(Enum):
    """Types of exit rules."""
    FIXED_PCT = "fixed_pct"
    ATR_STOP = "atr_stop"
    TRAILING_STOP = "trailing_stop"
    BREAK_EVEN = "break_even"
    TIME_STOP = "time_stop"


@dataclass
class FixedPctRule:
    """Fixed percentage stop loss and take profit."""
    type: str = "fixed_pct"
    sl_pct: float = 2.0       # Stop loss % below entry
    tp_pct: float = 4.0       # Take profit % above entry
    enabled: bool = True


@dataclass
class AtrStopRule:
    """ATR-based dynamic stop levels."""
    type: str = "atr_stop"
    sl_atr_mult: float = 1.5  # SL = entry - (ATR * mult)
    tp_atr_mult: float = 3.0  # TP = entry + (ATR * mult)
    atr_tf: str = "1h"        # Timeframe for ATR
    atr_period: int = 14      # ATR period
    enabled: bool = True


@dataclass
class TrailingStopRule:
    """Trailing stop that activates at profit threshold."""
    type: str = "trailing_stop"
    activation_pct: float = 1.5   # Activate when profit >= this %
    trail_pct: float = 1.0        # Trail distance as %
    enabled: bool = True


@dataclass
class BreakEvenRule:
    """Move stop loss to entry when profit threshold reached."""
    type: str = "break_even"
    at_profit_pct: float = 1.0    # Trigger when profit >= this %
    move_sl_to_entry: bool = True # Move SL to entry price
    buffer_pct: float = 0.1       # Optional buffer above entry
    enabled: bool = True


@dataclass
class TimeStopRule:
    """Close position after time window."""
    type: str = "time_stop"
    max_hold_hours: int = 48      # Max hold time
    force_exit: bool = True       # Force exit when time expires
    enabled: bool = True


# Union type for all rules
ExitRule = Union[FixedPctRule, AtrStopRule, TrailingStopRule, BreakEvenRule, TimeStopRule]


@dataclass
class ExitProfileV2:
    """
    Exit profile with multiple rule types.
    
    Rules are evaluated in order; first matching rule applies.
    """
    profile_id: str
    name: str
    description: str = ""
    rules: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 0  # Higher = more specific (pattern+symbol > pattern > global)
    
    # Scope matching
    symbol: Optional[str] = None    # None = all symbols
    pattern_id: Optional[str] = None  # None = all patterns
    confidence_min: Optional[float] = None  # Min pattern confidence
    
    # Metadata
    version: str = "2.0"
    enabled: bool = True


@dataclass
class ComputedExitLevels:
    """Computed exit levels for a position."""
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    trailing_active: bool = False
    trailing_sl: Optional[float] = None
    break_even_triggered: bool = False
    time_stop_due: Optional[str] = None
    rule_source: str = ""
    profile_id: str = ""


def parse_exit_rule(rule_dict: Dict) -> Optional[ExitRule]:
    """Parse a rule dictionary into typed rule object."""
    rule_type = rule_dict.get("type", "")
    
    if rule_type == "fixed_pct":
        return FixedPctRule(
            sl_pct=rule_dict.get("sl_pct", 2.0),
            tp_pct=rule_dict.get("tp_pct", 4.0),
            enabled=rule_dict.get("enabled", True)
        )
    elif rule_type == "atr_stop":
        return AtrStopRule(
            sl_atr_mult=rule_dict.get("sl_atr_mult", 1.5),
            tp_atr_mult=rule_dict.get("tp_atr_mult", 3.0),
            atr_tf=rule_dict.get("atr_tf", "1h"),
            atr_period=rule_dict.get("atr_period", 14),
            enabled=rule_dict.get("enabled", True)
        )
    elif rule_type == "trailing_stop":
        return TrailingStopRule(
            activation_pct=rule_dict.get("activation_pct", 1.5),
            trail_pct=rule_dict.get("trail_pct", 1.0),
            enabled=rule_dict.get("enabled", True)
        )
    elif rule_type == "break_even":
        return BreakEvenRule(
            at_profit_pct=rule_dict.get("at_profit_pct", 1.0),
            move_sl_to_entry=rule_dict.get("move_sl_to_entry", True),
            buffer_pct=rule_dict.get("buffer_pct", 0.1),
            enabled=rule_dict.get("enabled", True)
        )
    elif rule_type == "time_stop":
        return TimeStopRule(
            max_hold_hours=rule_dict.get("max_hold_hours", 48),
            force_exit=rule_dict.get("force_exit", True),
            enabled=rule_dict.get("enabled", True)
        )
    return None
