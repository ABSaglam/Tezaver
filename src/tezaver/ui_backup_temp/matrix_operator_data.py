"""
Matrix Operator Data Helpers v1

Parsing and data access functions for the Matrix Operator UI.
Keeps UI logic clean by providing simple data accessors.
"""

import json
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BundleInfo:
    """Info about an incident bundle."""
    path: str
    created_ts: str
    reason: str
    repo_commit: str
    files_count: int
    error: Optional[str] = None


def load_ndjson_tail(path: Path, max_lines: int = 500) -> List[Dict[str, Any]]:
    """
    Load last N lines from NDJSON file.
    Returns empty list if file missing/unreadable.
    """
    events = []
    
    if not path.exists():
        return events
    
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            tail_lines = lines[-max_lines:] if len(lines) > max_lines else lines
            
            for line in tail_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return events
    
    return events


def summarize_health(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract health summary from events.
    Picks latest event of each key type.
    """
    summary = {
        "preflight": None,
        "card_gate": None,
        "risk_limit": None,
        "reconcile": None,
        "incident_bundle": None,
    }
    
    # Scan events (already in chronological order, so last wins)
    for e in events:
        et = e.get("event_type", "")
        
        if et == "PREFLIGHT_EVAL":
            summary["preflight"] = {
                "decision": e.get("decision"),
                "ts": e.get("ts"),
                "failed_checks": e.get("failed_checks", []),
            }
        
        elif et == "CARD_GATE_EVAL":
            summary["card_gate"] = {
                "decision": e.get("gate") or e.get("decision"),
                "allow": e.get("allow"),
                "violations": e.get("violations", []),
                "ts": e.get("ts"),
            }
        
        elif et in ("RISK_LIMIT_CHECK", "RISK_LIMIT_BLOCK"):
            summary["risk_limit"] = {
                "decision": e.get("decision"),
                "allow": e.get("allow"),
                "total_notional": e.get("total_notional"),
                "ts": e.get("ts"),
            }
        
        elif et.startswith("RECON_"):
            summary["reconcile"] = {
                "ok": e.get("ok"),
                "warnings": e.get("warnings", []),
                "ts": e.get("ts"),
            }
        
        elif et == "INCIDENT_BUNDLE_EXPORTED":
            summary["incident_bundle"] = {
                "path": e.get("path"),
                "reason": e.get("reason"),
                "files_count": e.get("files_count"),
                "ts": e.get("ts"),
            }
    
    return summary


def list_incident_bundles(incident_dir: Path) -> List[BundleInfo]:
    """
    List incident bundle zips in directory, reading manifest from each.
    Returns empty list if dir missing.
    """
    bundles = []
    
    if not incident_dir.exists():
        return bundles
    
    for zip_path in sorted(incident_dir.glob("incident_bundle_*.zip"), reverse=True):
        info = read_bundle_manifest(zip_path)
        bundles.append(info)
    
    return bundles[:20]  # Limit to 20 most recent


def read_bundle_manifest(zip_path: Path) -> BundleInfo:
    """
    Read manifest.json from inside a zip bundle.
    Returns BundleInfo with error field if unreadable.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest_data = zf.read("manifest.json")
            manifest = json.loads(manifest_data)
            
            meta = manifest.get("metadata", {})
            files = manifest.get("files", [])
            
            return BundleInfo(
                path=str(zip_path),
                created_ts=meta.get("created_ts_utc", "unknown"),
                reason=meta.get("reason", "unknown"),
                repo_commit=meta.get("repo_commit", "unknown"),
                files_count=len(files),
            )
    except Exception as ex:
        return BundleInfo(
            path=str(zip_path),
            created_ts="unknown",
            reason="unknown",
            repo_commit="unknown",
            files_count=0,
            error=f"corrupt bundle: {ex}",
        )


def filter_events(
    events: List[Dict[str, Any]],
    event_types: Optional[List[str]] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Filter events by type and/or symbol/timeframe.
    """
    result = events
    
    if event_types:
        result = [e for e in result if e.get("event_type") in event_types]
    
    if symbol:
        result = [e for e in result if e.get("symbol") == symbol]
    
    if timeframe:
        result = [e for e in result if e.get("timeframe") == timeframe]
    
    return result
