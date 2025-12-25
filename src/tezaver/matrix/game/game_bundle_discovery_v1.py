"""
GAME Bundle Discovery v1.0.2
============================

Robust bundle discovery mechanism for Matrix GAME module.
Scans various sources (APPROVED, CANDIDATES, GOLDEN, MANUAL) for manifests.
Uses rglob for reliable recursive scanning and supports legacy/failed filtering.
"""

import os
import json
import logging
import re
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
        ts = self.created_ts or "-"
        return f"{self.bundle_id} | {s} | {t} | {self.source} | {ts}"

@dataclass
class DiscoveryResult:
    """Result of a discovery operation."""
    bundles: List[BundleRef] = field(default_factory=list)
    scanned_roots: List[str] = field(default_factory=list) # Actual roots scanned
    missing_roots: List[str] = field(default_factory=list) # Expected but missing roots
    errors: List[str] = field(default_factory=list)
    counts_by_source: Dict[str, int] = field(default_factory=dict)
    excluded_counts: Dict[str, int] = field(default_factory=lambda: {"legacy": 0, "failed": 0, "fixtures": 0})
    
    # Deprecated compatibility
    @property
    def scanned_paths(self) -> List[str]:
        return self.scanned_roots

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

def resolve_repo_root(bus_root: str) -> str:
    """Try to find repo root for fixtures."""
    bus = Path(bus_root)
    if (bus / ".git").exists():
        return str(bus)
    # Check parent
    if (bus.parent / ".git").exists():
        return str(bus.parent)
    return bus_root

def load_bundle_from_manual_path(path_str: str) -> Optional[BundleRef]:
    """
    Load a bundle from a manual path (file or directory).
    """
    path = Path(path_str)
    if not path.exists():
        return None
        
    manifest_path = None
    bundle_root = None
    
    if path.is_file() and "manifest" in path.name and path.suffix == ".json":
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


def discover_bundles(
    bus_root: str, 
    source: str,
    include_legacy: bool = False,
    include_failed: bool = False
) -> DiscoveryResult:
    """
    Discover bundles from specific source using rglob and filtering.
    """
    result = DiscoveryResult()
    root = Path(bus_root)
    
    # Identify Search Roots
    search_roots = []
    
    if source == "APPROVED":
        # 1. New Standard Library (Protocol V1)
        # Assuming project root relative to bus root or hardcoded?
        # Resolving via known path structure for now
        candidates 
        # Resolving Matrix Library relative to cwd or BUS?
        # Let's try to resolve from TEZAVER_HOME/src/tezaver/matrix/library/bundles
        if "TEZAVER_HOME" in os.environ:
             lib_path = Path(os.environ["TEZAVER_HOME"]) / "src/tezaver/matrix/library/bundles"
             search_roots.append(lib_path)
        else:
             # Fallback: relative to .tezaver_bus? No, project specific.
             # Fallback to CWD/src/tezaver/matrix/library/bundles
             search_roots.append(Path.cwd() / "src/tezaver/matrix/library/bundles")
             
        # 2. Legacy Output (Backwards Compat)
        search_roots.append(root / "out" / "matrix_approved")
        
    elif source == "CANDIDATES":
        search_roots.append(root / "out" / "matrix_candidates")
    elif source == "GOLDEN":
        repo_root = resolve_repo_root(bus_root)
        search_roots.append(Path(repo_root) / "_fixtures")
        search_roots.append(Path(repo_root) / "tests" / "_fixtures")
        search_roots.append(Path(repo_root) / "tests" / "matrix" / "_fixtures")

    # Scan
    found_bundles = []
    
    for s_root in search_roots:
        if not s_root.exists():
            if source == "APPROVED": # Notify specifically for Approved
                result.missing_roots.append(str(s_root))
            elif source == "CANDIDATES":
                result.missing_roots.append(str(s_root))
            # Golden often has missing checked paths, ignore noise unless all missing
            continue
            
        result.scanned_roots.append(str(s_root))
        
        # rglob for robustness
        # Set is used to deduplicate paths if patterns overlap
        manifest_files = set(s_root.rglob("manifest*.json"))
        # Also catch *manifest*.json just in case
        manifest_files.update(s_root.rglob("*manifest*.json"))
        
        for m_path in manifest_files:
            # FILTERING
            path_str = str(m_path)
            
            # Legacy Check
            if "/_legacy/" in path_str and not include_legacy:
                result.excluded_counts["legacy"] += 1
                continue
                
            # Failed Check
            if "/_failed/" in path_str and not include_failed:
                result.excluded_counts["failed"] += 1
                continue
            
            # Fixtures in Candidates exclusion (if scanning candidates, ignore internal fixtures)
            if source == "CANDIDATES" and "/_fixtures/" in path_str:
                result.excluded_counts["fixtures"] += 1
                continue

            try:
                b_ref = _parse_manifest(m_path, m_path.parent, source)
                if b_ref:
                    found_bundles.append(b_ref)
            except Exception as e:
                msg = f"Error parsing {m_path}: {str(e)}"
                if len(result.errors) < 10:
                    result.errors.append(msg)

    # Deduplication Logic
    # 1. Sort by created_ts desc (newest first)
    found_bundles.sort(key=lambda x: x.created_ts or "", reverse=True)
    
    # 2. Filter unique by bundle_id.
    # Newest (by TS) wins. If no TS, then sorting was by empty string, essentially file order.
    # To improve robust dedup if ts missing, rely on bundle_root name maybe? 
    # But usually just keep the first one found if duplicate IDs.
    
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
            # If folder is like "bundle_v1", go up one level
            if root.name.startswith("bundle_v"):
                 # e.g. BTCUSDT/15m/bundle_v1 -> check parents
                 # heuristic: construct from parent names?
                 # Better: just use root name + parent info?
                 # Or just root name.
                 bid = root.name
            else:
                 bid = root.name
        
        # If still generic 'bundle_v1', prepend parent name
        if bid == "bundle_v1" or bid.startswith("bundle_v1_"):
             # Use timestamp suffix if in folder name?
             # Let's prefix with parent (15m) and g-parent(Symbol)
             # root.parent = 15m, root.parent.parent = BTCUSDT
             try:
                 bid = f"{root.parent.parent.name}_{root.parent.name}_{bid}"
             except:
                 pass

        # Symbol/TF
        symbol = data.get("symbol")
        tf = data.get("timeframe")
        
        # Fallback Inference from Path
        if not symbol or not tf:
            parts = path.parts
            for i in range(len(parts)-1, -1, -1):
                part = parts[i]
                if not tf and re.match(r"^\d+[mhd]$", part):
                    tf = part
                    if not symbol and i > 0:
                        symbol = parts[i-1]
                        
            if not symbol:
                for part in reversed(parts):
                    if re.match(r"^[A-Z0-9]{3,8}$", part) and part not in ["OUT", "MATRIX", "APPROVED", "CANDIDATES", "BUNDLE", "V1", "_LEGACY", "_FAILED"]:
                        symbol = part
                        break

        # Fallback Inference from Bundle ID
        if bid and (not symbol or not tf):
            if not tf:
                m = re.search(r"[_\-](\d+[mhd])[_\-]", bid)
                if m: tf = m.group(1)
            
            if not symbol:
                tokens = re.split(r"[_\-]", bid)
                if tokens: symbol = tokens[0]
        
        # Created TS
        ts = data.get("created_ts") or data.get("created_at") or data.get("event_time_iso") or data.get("build_ts")
        
        # PROTOCOL V1 SUPPORT
        # If strict V1, use its fields directly
        if data.get("protocol_version") == "1.0":
            bid = data["bundle_id"]
            symbol = data["symbol"]
            tf = data["timeframe"]
            ts = data["created_ts"]
            # Source handling
            if "source_system" in data:
                 source_val = data["source_system"]
                 if "foundry" in source_val: source = "APPROVED" # Map to APPROVED by default?
                 # Actually preserve the source passed in argument unless overridden?
                 # Let's keep the passed source argument usually, but maybe annotate.
        
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
        raise
