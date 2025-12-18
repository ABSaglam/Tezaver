# Tezaver Bulut - Entry Sizing Profile Schema v1
"""
Schema for Entry Sizing Profiles.
Determines position size (notional) and leverage based on scope.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Literal

SCHEMA_VERSION = "entry_sizing_profile_v1"

@dataclass
class EntrySizingRuleV1:
    type: Literal["fixed_notional", "pct_of_cap"]
    
    # For fixed_notional
    fixed_notional_usdt: Optional[float] = None
    
    # For pct_of_cap
    pct: Optional[float] = None # 0.0 - 100.0
    cap_ref: Optional[Literal["MAX_CELL_NOTIONAL", "MAINNET_PILOT_CAP", "MAX_TOTAL_NOTIONAL"]] = None
    
    # Optional overrides
    leverage: Optional[int] = None # 1..125
    max_entries_per_cycle_override: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "fixed_notional_usdt": self.fixed_notional_usdt,
            "pct": self.pct,
            "cap_ref": self.cap_ref,
            "leverage": self.leverage,
            "max_entries_per_cycle_override": self.max_entries_per_cycle_override
        }

@dataclass
class EntrySizingScopeV1:
    symbol: Optional[str] = None      # Specific symbol or None for any
    pattern_id: Optional[str] = None  # Specific pattern or None for any
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "pattern_id": self.pattern_id
        }

@dataclass
class EntrySizingSafetyV1:
    min_notional_usdt: Optional[float] = None
    max_notional_usdt: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "min_notional_usdt": self.min_notional_usdt,
            "max_notional_usdt": self.max_notional_usdt
        }

@dataclass
class EntrySizingProfileV1:
    profile_id: str
    version: str # e.g. "1.0"
    priority: int # Higher wins
    scope: EntrySizingScopeV1
    rule: EntrySizingRuleV1
    safety: EntrySizingSafetyV1 = field(default_factory=EntrySizingSafetyV1)
    
    @property
    def schema(self) -> str:
        return SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "profile_id": self.profile_id,
            "version": self.version,
            "priority": self.priority,
            "scope": self.scope.to_dict(),
            "rule": self.rule.to_dict(),
            "safety": self.safety.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional["EntrySizingProfileV1"]:
        if data.get("schema") != SCHEMA_VERSION:
            return None
            
        try:
            scope_data = data.get("scope", {})
            scope = EntrySizingScopeV1(
                symbol=scope_data.get("symbol"),
                pattern_id=scope_data.get("pattern_id")
            )
            
            rule_data = data.get("rule", {})
            rule = EntrySizingRuleV1(
                type=rule_data.get("type"),
                fixed_notional_usdt=rule_data.get("fixed_notional_usdt"),
                pct=rule_data.get("pct"),
                cap_ref=rule_data.get("cap_ref"),
                leverage=rule_data.get("leverage"),
                max_entries_per_cycle_override=rule_data.get("max_entries_per_cycle_override")
            )
            
            safety_data = data.get("safety", {})
            safety = EntrySizingSafetyV1(
                min_notional_usdt=safety_data.get("min_notional_usdt"),
                max_notional_usdt=safety_data.get("max_notional_usdt")
            )
            
            return cls(
                profile_id=data.get("profile_id"),
                version=data.get("version"),
                priority=data.get("priority", 0),
                scope=scope,
                rule=rule,
                safety=safety
            )
        except Exception as e:
            print(f"Error parsing EntrySizingProfileV1: {e}")
            return None
