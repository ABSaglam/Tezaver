"""
MX-5270: Safety Certificate Writer - Generates run-scoped audit artifacts (JSON/MD).
"""
import os
import json
from datetime import datetime
from typing import Dict

def write_safety_certificate(run_dir: str, sweep_results: Dict):
    """
    Generate safety_certificate_v1.json and safety_certificate_v1.md in reports/
    """
    reports_dir = os.path.join(run_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # 1. Metadata extraction from meta.json if available
    meta = {}
    meta_path = os.path.join(run_dir, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
        except:
            pass
            
    certificate = {
        "version": "safety_certificate_v1",
        "ts": datetime.now().isoformat(),
        "run_id": meta.get("run_id", os.path.basename(run_dir)),
        "engine_version": meta.get("engine_version", "v4"),
        "build_commit": meta.get("build_commit", "unknown"),
        "config_signature": meta.get("config_signature", "unknown"),
        "results": sweep_results
    }
    
    # Write JSON
    json_path = os.path.join(reports_dir, "safety_certificate_v1.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(certificate, f, indent=2)
        
    # Write Markdown
    md_path = os.path.join(reports_dir, "safety_certificate_v1.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(generate_md_report(certificate))
        
    return json_path

def generate_md_report(cert: Dict) -> str:
    res = cert["results"]
    verdict_emoji = "✅" if res["verdict"] == "PASS" else "❌"
    
    lines = [
        f"# Matrix Safety Certificate - {cert['run_id']}",
        f"**Verdict:** {verdict_emoji} {res['verdict']}",
        f"**Active Stage:** {res['active_stage']}",
        f"**Generated at:** {cert['ts']}",
        "",
        "## Summary Counts",
        f"- 🟩 GREEN: {res['counts']['GREEN']}",
        f"- 🟨 YELLOW: {res['counts']['YELLOW']}",
        f"- 🟥 RED: {res['counts']['RED']}",
        f"- ⬜ GRAY/LOCKED: {res['counts']['GRAY'] + res['counts']['LOCKED']}",
        ""
    ]
    
    if res["blockers"]:
        lines.append("## ❌ Blockers")
        for b in res["blockers"]:
            lines.append(f"- **{b['mx']}**: {b['name']} ({b['reason']})")
        lines.append("")
        
    if res["warnings"]:
        lines.append("## ⚠️ Warnings")
        for w in res["warnings"]:
            lines.append(f"- **{w['mx']}**: {w['name']} ({w['reason']})")
        lines.append("")
        
    lines.extend([
        "## Protocol Details",
        "| MX | Protocol | Declared | Effective | Evidence OK | Missing |",
        "|---|---|---|---|---|---|",
    ])
    
    for p in res["protocols"]:
        ev_ok = "✅" if p["evidence_ok"] else "❌"
        lines.append(f"| {p['mx']} | {p['name']} | {p['declared_status']} | {p['effective_status']} | {ev_ok} | {p['missing_summary']} |")
        
    return "\n".join(lines)
