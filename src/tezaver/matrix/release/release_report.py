import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def write_release_report(run_dir: Path, gate_result: Dict[str, Any]) -> Path:
    """
    MX-5190: Saves the release gate verdict as a persistent report.
    Tr: Release gate sonucunu kalıcı bir rapor (release_report_v1.json) olarak kaydeder.
    """
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = reports_dir / "release_report_v1.json"
    
    # Extract blocking vs warnings
    blocking = [c["name"] for c in gate_result.get("checks", []) if c["status"] == "FAIL" and c.get("severity") == "CRITICAL"]
    warnings = [c["name"] for c in gate_result.get("checks", []) if c["status"] == "FAIL" and c.get("severity") != "CRITICAL"]
    
    report = {
        "run_id": run_dir.name,
        "ts": datetime.utcnow().isoformat() + "Z",
        "version": "v1",
        "overall_ok": gate_result.get("ok", False),
        "active_stage": gate_result.get("active_stage", "UNKNOWN"),
        "assumed_stage": gate_result.get("assumed_stage", False),
        "blocking_protocols": gate_result.get("blocking_protocols", blocking),
        "warnings": gate_result.get("warnings", warnings),
        "summary": gate_result.get("summary", "No summary provided")
    }
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
        
    return report_path
