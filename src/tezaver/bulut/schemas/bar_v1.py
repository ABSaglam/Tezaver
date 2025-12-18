# Tezaver Bulut - Bar v1 Schema
"""
Schema definition for OHLCV Bar v1.
Used for 15m closed bars and aggregation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class BarV1:
    """
    OHLCV Bar v1 Schema.
    
    Structure:
    {
      "schema":"bar_v1",
      "symbol":"BTCUSDT",
      "tf":"15m",
      "open_ts":"iso",
      "close_ts":"iso",
      "o":float,"h":float,"l":float,"c":float,"v":float,
      "is_closed":true
    }
    """
    symbol: str
    tf: str
    open_ts: datetime
    close_ts: datetime
    o: float
    h: float
    l: float
    c: float
    v: float
    is_closed: bool = True
    
    @property
    def schema(self) -> str:
        return "bar_v1"
        
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "symbol": self.symbol,
            "tf": self.tf,
            "open_ts": self.open_ts.isoformat(),
            "close_ts": self.close_ts.isoformat(),
            "o": self.o,
            "h": self.h,
            "l": self.l,
            "c": self.c,
            "v": self.v,
            "is_closed": self.is_closed,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional["BarV1"]:
        if data.get("schema") != "bar_v1":
            return None
            
        try:
            return cls(
                symbol=data.get("symbol", ""),
                tf=data.get("tf", "15m"),
                open_ts=datetime.fromisoformat(data.get("open_ts").replace("Z", "+00:00")),
                close_ts=datetime.fromisoformat(data.get("close_ts").replace("Z", "+00:00")),
                o=float(data.get("o", 0.0)),
                h=float(data.get("h", 0.0)),
                l=float(data.get("l", 0.0)),
                c=float(data.get("c", 0.0)),
                v=float(data.get("v", 0.0)),
                is_closed=data.get("is_closed", True),
            )
        except Exception:
            return None
