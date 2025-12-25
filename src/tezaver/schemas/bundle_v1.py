
"""
Tezaver Bundle Protocol V1
==========================

Defines the strict schema and naming conventions for bundles moving 
from Foundry (Dokumhane) to Matrix via the Bus.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
import re
import json
from datetime import datetime

PROTOCOL_VERSION = "1.0"

@dataclass
class BundleManifestV1:
    """
    Strict Schema for Bundle Manifest V1.
    """
    protocol_version: str
    bundle_id: str
    source_system: str
    created_ts: str
    symbol: str
    timeframe: str
    data_hash: str
    status: str
    suffix_code: str
    
    # Optional metadata
    summary: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BundleManifestV1":
        # Validate required fields
        required = [
            "protocol_version", "bundle_id", "source_system", 
            "created_ts", "symbol", "timeframe", "data_hash", 
            "status", "suffix_code"
        ]
        
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"Manifest V1 missing fields: {missing}")
            
        if data["protocol_version"] != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {data.get('protocol_version')}")
            
        return cls(
            protocol_version=data["protocol_version"],
            bundle_id=data["bundle_id"],
            source_system=data["source_system"],
            created_ts=data["created_ts"],
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            data_hash=data["data_hash"],
            status=data["status"],
            suffix_code=data["suffix_code"],
            summary=data.get("summary"),
            details=data.get("details", {})
        )

class BundleNamingV1:
    """
    Implements the strict naming convention:
    {SYMBOL}_{TF}_{YYWW}_{VER}_{SUFFIX}
    
    Example: BTC_15m_2551_A_D
    """
    
    # Regex for validation
    # Group 1: Symbol (Alphanumeric)
    # Group 2: Timeframe (digits + m/h)
    # Group 3: YYWW (4 digits)
    # Group 4: Version (A-Z)
    # Group 5: Suffix (D, DG, DGW, DGWL)
    NAME_PATTERN = re.compile(r"^([A-Z0-9]+)_(\d+[mh])_(\d{4})_([A-Z])_([DGWL]+)$")
    
    @staticmethod
    def parse_id(bundle_id: str) -> Optional[Dict[str, str]]:
        match = BundleNamingV1.NAME_PATTERN.match(bundle_id)
        if not match:
            return None
            
        return {
            "symbol": match.group(1),
            "timeframe": match.group(2),
            "yyww": match.group(3),
            "ver": match.group(4),
            "suffix": match.group(5)
        }
        
    @staticmethod
    def generate_id(symbol: str, timeframe: str, dt: datetime, version: str, suffix: str) -> str:
        """
        Generate a compliant ID.
        dt: datetime object to extract YY and Week Number.
        """
        # YY
        year_short = dt.strftime("%y")
        # WW (ISO week number)
        week_num = dt.isocalendar()[1]
        yyww = f"{year_short}{week_num:02d}"
        
        # Upper case inputs
        sym_clean = symbol.upper()
        ver_clean = version.upper()
        suf_clean = suffix.upper()
        
        return f"{sym_clean}_{timeframe}_{yyww}_{ver_clean}_{suf_clean}"
        
    @staticmethod
    def validate_id(bundle_id: str) -> bool:
        return BundleNamingV1.NAME_PATTERN.match(bundle_id) is not None

