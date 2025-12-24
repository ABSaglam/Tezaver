
"""
GAME Bundle Discovery v1
=========================

Robust bundle discovery mechanism for Matrix GAME module.
Scans various sources (APPROVED, CANDIDATES, GOLDEN, MANUAL) for manifests.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class BundleRef:
    """Reference to a discoverable bundle."""
    bundle_id: str
    symbol: Optional[str]
    timeframe: Optional[str]
    manifest_path: str
    bundle_root: str
    source: str  # "APPROVED"|"CANDIDATES"|"GOLDEN"|"MANUAL"
    created_ts: Optional[str]

    @property
    def label(self) -> str:
        """Formatted label for UI."""
        s = self.symbol or "?"
        t = self.timeframe or "?"
        return f"{self.bundle_id} | {s} | {t} | {self.source}"

@dataclass
class DiscoveryResult:
    """Result of a discovery operation."""
    bundles: List[BundleRef] = field(default_factory=list)
    scanned_paths: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    counts_by_source: Dict[str, int] = field(default_factory=dict)

def resolve_bus_root() -> str:
    """
    Resolve the root directory for scanning.
    Priority: TEZAVER_BUS > TEZAVER_HOME > git root > cwd
    """
    # 1. Env vars
    if "TEZAVER_BUS" in os.environ:
        return os.environ["TEZAVER_BUS"]
    if "TEZAVER_HOME" in os.environ:
        return os.environ["TEZAVER_HOME"]
    
    # 2. Repo root (naive check)
    current = Path.cwd()
    if (current / ".git").exists():
        return str(current)
    
    # 3. Fallback
    return str(current)

def load_bundle_from_manual_path(path_str: str) -> Optional[BundleRef]:
    """
    Load a bundle from a manual path (file or directory).
    """
    path = Path(path_str)
    if not path.exists():
        return None
        
    manifest_path = None
    bundle_root = None
    
    if path.is_file() and path.name.startswith("manifest") and path.suffix == ".json":
        manifest_path = path
        bundle_root = path.parent
    elif path.is_dir():
        # Look for manifest.json (max depth 2)
        candidates = list(path.glob("manifest*.json")) + list(path.glob("*/manifest*.json"))
        if candidates:
            manifest_path = candidates[0]
            bundle_root = manifest_path.parent
            
    if not manifest_path:
        return None
        
    return _parse_manifest(manifest_path, bundle_root, "MANUAL")


def discover_bundles(bus_root: str, source: str) -> DiscoveryResult:
    """
    Discover bundles from specific source.
    """
    result = DiscoveryResult()
    root = Path(bus_root)
    
    patterns = []
    
    # Define patterns based on source
    if source == "APPROVED":
        patterns = [
            "out/matrix_approved/**/manifest*.json",
            "out/matrix_approved/**/*manifest*.json"
        ]
    elif source == "CANDIDATES":
        patterns = [
            "out/matrix_candidates/**/manifest*.json",
            "out/matrix_candidates/**/*manifest*.json"
        ]
    elif source == "GOLDEN":
        patterns = [
           "_fixtures/**/manifest*.json",
           "tests/**/_fixtures/**/manifest*.json" 
        ]
    
    # Add globs to result
    for p in patterns:
        result.scanned_paths.append(str(root / p))
        
    found_bundles = []
    
    for pattern in patterns:
        for m_path in root.glob(pattern):
            try:
                b_ref = _parse_manifest(m_path, m_path.parent, source)
                if b_ref:
                    found_bundles.append(b_ref)
            except Exception as e:
                # Log error uniquely
                msg = f"Error parsing {m_path.name}: {str(e)}"
                if len(result.errors) < 10:
                    result.errors.append(msg)

    # Deduplication Logic
    # 1. Sort by created_ts desc (newest first)
    found_bundles.sort(key=lambda x: x.created_ts or "", reverse=True)
    
    # 2. Filter unique by bundle_id if requested, but usually source is singular here.
    # If we want to return distinct list:
    unique_map = {}
    for b in found_bundles:
        if b.bundle_id not in unique_map:
            unique_map[b.bundle_id] = b
            
    final_list = list(unique_map.values())
    
    # Re-sort final list
    final_list.sort(key=lambda x: x.created_ts or "", reverse=True)
    
    result.bundles = final_list
    result.counts_by_source[source] = len(final_list)
    
    return result

def _parse_manifest(path: Path, root: Path, source: str) -> Optional[BundleRef]:
    """Helper to parse a manifest file with best-effort strategy."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            
        # Best effort ID
        bid = data.get("bundle_id") or data.get("id")
        if not bid and "manifest" in data:
            bid = data["manifest"].get("bundle_id")
            
        # Fallback ID: directory name
        if not bid:
            bid = root.name
            
        # Symbol/TF
        symbol = data.get("symbol")
        tf = data.get("timeframe")
        
        # Created TS
        ts = data.get("created_ts") or data.get("created_at") or data.get("event_time_iso")
        
        return BundleRef(
            bundle_id=bid,
            symbol=symbol,
            timeframe=tf,
            manifest_path=str(path),
            bundle_root=str(root),
            source=source,
            created_ts=ts
        )
    except Exception:
        raise # Let caller handle logging
