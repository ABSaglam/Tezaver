# Tezaver Bulut - Pattern Pack Schema v1
"""
Schema definition for PatternPack v1.

PatternPack is the intelligence payload from Tezaver Mac.
Bulut only needs to verify "pack exists and is valid".
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


SCHEMA_VERSION = "pattern_pack_v1"


@dataclass
class PatternEntry:
    """Single pattern entry within a pack."""
    pattern_id: str
    tf: str  # e.g., "15m"
    kind: str  # e.g., "SILVER_ENTRY", "RALLY_START"
    payload: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "tf": self.tf,
            "kind": self.kind,
            "payload": self.payload,
        }


@dataclass
class PatternPackV1:
    """
    Pattern Pack v1 Schema.
    
    Structure:
    {
        "schema": "pattern_pack_v1",
        "pack_id": "string",
        "built_at": "iso",
        "hash": "string",
        "symbols": ["..."],
        "timeframes": ["15m", "1h", "4h"],
        "patterns_by_symbol": {
            "BTCUSDT": [{"pattern_id": "...", "tf": "15m", "kind": "...", "payload": {}}]
        }
    }
    """
    pack_id: str
    built_at: datetime
    hash: str
    symbols: list[str]
    timeframes: list[str]
    patterns_by_symbol: dict[str, list[PatternEntry]] = field(default_factory=dict)
    
    @property
    def schema(self) -> str:
        return SCHEMA_VERSION
    
    def get_patterns_for_symbol(self, symbol: str) -> list[PatternEntry]:
        """Get all patterns for a symbol."""
        return self.patterns_by_symbol.get(symbol, [])
    
    def has_patterns_for_symbol(self, symbol: str) -> bool:
        """Check if pack contains patterns for symbol."""
        return symbol in self.patterns_by_symbol and len(self.patterns_by_symbol[symbol]) > 0
    
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "pack_id": self.pack_id,
            "built_at": self.built_at.isoformat() if isinstance(self.built_at, datetime) else self.built_at,
            "hash": self.hash,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "patterns_by_symbol": {
                sym: [p.to_dict() for p in patterns]
                for sym, patterns in self.patterns_by_symbol.items()
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional["PatternPackV1"]:
        """Parse from dictionary."""
        if data.get("schema") != SCHEMA_VERSION:
            return None
        
        try:
            built_at = data.get("built_at", "")
            if isinstance(built_at, str):
                built_at = datetime.fromisoformat(built_at.replace("Z", "+00:00"))
            
            patterns_by_symbol = {}
            raw_patterns = data.get("patterns_by_symbol", {})
            for symbol, entries in raw_patterns.items():
                patterns_by_symbol[symbol] = [
                    PatternEntry(
                        pattern_id=e.get("pattern_id", ""),
                        tf=e.get("tf", ""),
                        kind=e.get("kind", ""),
                        payload=e.get("payload", {}),
                    )
                    for e in entries
                ]
            
            return cls(
                pack_id=data.get("pack_id", ""),
                built_at=built_at,
                hash=data.get("hash", ""),
                symbols=data.get("symbols", []),
                timeframes=data.get("timeframes", []),
                patterns_by_symbol=patterns_by_symbol,
            )
        except Exception:
            return None


def validate_pattern_pack(data: dict) -> tuple[bool, Optional[str]]:
    """
    Validate pattern pack structure.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Not a dictionary"
    
    if data.get("schema") != SCHEMA_VERSION:
        return False, f"Invalid schema: expected {SCHEMA_VERSION}"
    
    required = ["pack_id", "built_at", "hash", "symbols", "timeframes"]
    for key in required:
        if key not in data:
            return False, f"Missing required field: {key}"
    
    if not isinstance(data.get("symbols"), list):
        return False, "symbols must be a list"
    
    if not isinstance(data.get("timeframes"), list):
        return False, "timeframes must be a list"
    
    return True, None
