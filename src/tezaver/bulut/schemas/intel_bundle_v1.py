# Tezaver Bulut - Intel Bundle Schema V1
"""
Schema for Intel Bundles (Pattern Packs + Meta).
Ensures strict contract for transferring intelligence from Mac to Cloud.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import json

@dataclass
class IntelArtifactV1:
    """Detailed artifact within the bundle."""
    name: str # e.g. "pattern_pack.json", "trustworthy_patterns.json"
    path: str # relative path inside bundle or just filename if flat
    sha256: str
    size_bytes: int = 0

@dataclass
class IntelCoverageV1:
    """Coverage metadata."""
    symbols: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=list)

@dataclass
class IntelBundleV1:
    """
    Root contract for an Intel Bundle.
    """
    schema: str = "intel_bundle_v1"
    bundle_id: str = "" # UUID or Timestamp-based ID
    built_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    producer: str = "tezaver_mac"
    
    # Integrity
    bundle_hash: str = "" # SHA256 of the core content (artifacts)
    
    # Content
    artifacts: List[IntelArtifactV1] = field(default_factory=list)
    coverage: IntelCoverageV1 = field(default_factory=IntelCoverageV1)
    
    # Metadata
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Signature (Simple hash verification for now)
    signature: Dict[str, str] = field(default_factory=lambda: {"algo": "sha256", "value": ""})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "bundle_id": self.bundle_id,
            "built_at": self.built_at.isoformat(),
            "producer": self.producer,
            "bundle_hash": self.bundle_hash,
            "artifacts": [
                {
                    "name": a.name,
                    "path": a.path,
                    "sha256": a.sha256,
                    "size_bytes": a.size_bytes
                } for a in self.artifacts
            ],
            "coverage": {
                "symbols": self.coverage.symbols,
                "timeframes": self.coverage.timeframes
            },
            "notes": self.notes,
            "tags": self.tags,
            "signature": self.signature
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntelBundleV1':
        inst = cls(
            schema=data.get("schema", "intel_bundle_v1"),
            bundle_id=data.get("bundle_id", ""),
            built_at=datetime.fromisoformat(data.get("built_at", datetime.now(timezone.utc).isoformat())),
            producer=data.get("producer", "tezaver_mac"),
            bundle_hash=data.get("bundle_hash", ""),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            signature=data.get("signature", {"algo": "sha256", "value": ""})
        )
        
        # Artifacts
        for a in data.get("artifacts", []):
            inst.artifacts.append(IntelArtifactV1(
                name=a["name"],
                path=a["path"],
                sha256=a["sha256"],
                size_bytes=a.get("size_bytes", 0)
            ))
            
        # Coverage
        cov = data.get("coverage", {})
        inst.coverage = IntelCoverageV1(
            symbols=cov.get("symbols", []),
            timeframes=cov.get("timeframes", [])
        )
        
        return inst
