# Tezaver Bulut - Exit Profile Schema
"""
Schema handling for Exit Profile rules (sl/tp/time).
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import json

@dataclass
class ExitScope:
    symbol: Optional[str] = None
    pattern_id: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)

@dataclass
class ExitRule:
    type: str # 'fixed_pct', 'time_stop'
    # Optional params
    sl_pct: Optional[float] = None
    tp_pct: Optional[float] = None
    max_bars: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)

@dataclass
class ExitProfileV1:
    profile_id: str
    version: str
    priority: int
    rules: List[ExitRule]
    scope: ExitScope = field(default_factory=ExitScope)
    schema: str = "exit_profile_v1"
    
    def to_dict(self):
        return {
            "schema": self.schema,
            "profile_id": self.profile_id,
            "version": self.version,
            "scope": self.scope.to_dict(),
            "rules": [r.to_dict() for r in self.rules],
            "priority": self.priority
        }

    @classmethod
    def from_dict(cls, d: dict):
        rules = [ExitRule.from_dict(r) for r in d.get("rules", [])]
        scope = ExitScope.from_dict(d.get("scope", {}))
        return cls(
            profile_id=d.get("profile_id", "default"),
            version=d.get("version", "v1"),
            priority=d.get("priority", 0),
            rules=rules,
            scope=scope,
            schema=d.get("schema", "exit_profile_v1")
        )

# Default global profile
DEFAULT_EXIT_PROFILE = ExitProfileV1(
    profile_id="builtin_default",
    version="v1",
    priority=-1,
    rules=[
        ExitRule(type="fixed_pct", sl_pct=1.0, tp_pct=2.0),
        ExitRule(type="time_stop", max_bars=16) 
    ],
    scope=ExitScope()
)
