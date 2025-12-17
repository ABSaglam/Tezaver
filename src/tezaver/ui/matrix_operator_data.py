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


def summarize_locks_from_ndjson(events_path: Path, tail_n: int = 2000) -> Dict[str, Dict[str, Any]]:
    """
    Extract lock states from NDJSON telemetry events.
    
    Returns:
        {
            "preflight": {"state": "PASS/WARN/BLOCK/UNKNOWN", "ts": "...", "reason": "..."},
            "card_gate": {...},
            "risk": {...},
            "reconcile": {"state": "UNKNOWN", ...},
            "last_block_reason": "..." or None
        }
    """
    result = {
        "preflight": {"state": "UNKNOWN", "ts": None, "reason": None},
        "card_gate": {"state": "UNKNOWN", "ts": None, "reason": None},
        "risk": {"state": "UNKNOWN", "ts": None, "reason": None},
        "reconcile": {"state": "UNKNOWN", "ts": None, "reason": None},
        "last_block_reason": None,
    }
    
    if not events_path.exists():
        return result
    
    events = load_ndjson_tail(events_path, max_lines=tail_n)
    if not events:
        return result
    
    # Scan events (chronological, last wins)
    for e in events:
        et = e.get("event_type", "")
        ts = e.get("ts")
        
        # PREFLIGHT
        if et == "PREFLIGHT_EVAL":
            decision = e.get("decision", "").upper()
            failed = e.get("failed_checks", [])
            if decision in ("PASS", "WARN", "BLOCK"):
                result["preflight"] = {
                    "state": decision,
                    "ts": ts,
                    "reason": ", ".join(failed) if failed else None,
                }
                if decision == "BLOCK":
                    result["last_block_reason"] = f"Preflight: {', '.join(failed)}"
        
        # CARD_GATE
        elif et == "CARD_GATE_EVAL":
            allow = e.get("allow")
            gate = e.get("gate") or e.get("decision", "")
            violations = e.get("violations", [])
            
            if allow is True:
                state = "PASS"
            elif allow is False:
                state = "BLOCK"
            elif gate.upper() in ("PASS", "WARN", "BLOCK"):
                state = gate.upper()
            else:
                state = "UNKNOWN"
            
            result["card_gate"] = {
                "state": state,
                "ts": ts,
                "reason": ", ".join(str(v) for v in violations) if violations else None,
            }
            if state == "BLOCK":
                result["last_block_reason"] = f"CardGate: {', '.join(str(v) for v in violations)}"
        
        # RISK
        elif et in ("RISK_LIMIT_CHECK", "RISK_LIMIT_BLOCK", "RISK_LIMIT_EVAL"):
            allow = e.get("allow")
            decision = e.get("decision", "").upper()
            
            if allow is True or decision == "PASS":
                state = "PASS"
            elif allow is False or decision == "BLOCK":
                state = "BLOCK"
            elif decision == "WARN":
                state = "WARN"
            else:
                state = "UNKNOWN"
            
            reason = e.get("reason") or e.get("message")
            result["risk"] = {
                "state": state,
                "ts": ts,
                "reason": reason,
            }
            if state == "BLOCK":
                result["last_block_reason"] = f"Risk: {reason or 'limit exceeded'}"
        
        # RECONCILE (M2'de gerçek yapılacak)
        elif et.startswith("RECON_") or et == "RECONCILE_CHECK":
            ok = e.get("ok")
            warnings = e.get("warnings", [])
            
            if ok is True and not warnings:
                state = "PASS"
            elif ok is True and warnings:
                state = "WARN"
            elif ok is False:
                state = "BLOCK"
            else:
                state = "UNKNOWN"
            
            result["reconcile"] = {
                "state": state,
                "ts": ts,
                "reason": ", ".join(warnings) if warnings else None,
            }
        
        # INCIDENT BUNDLE -> last block reason
        elif et == "INCIDENT_BUNDLE_EXPORTED":
            reason = e.get("reason")
            if reason:
                result["last_block_reason"] = reason
    
    return result

