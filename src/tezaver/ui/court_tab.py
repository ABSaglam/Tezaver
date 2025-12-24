
import streamlit as st
import json
import os
import glob
from pathlib import Path
from datetime import datetime

def render_court_tab():
    st.header("Matrix Court Verdicts ⚖️")
    
    # 1. Scan for Runs
    # Path: out/matrix_runs/war/POOL_*/reports/pool_court_verdict_v1.json
    # We target "war" stage for now as per "cloud_loop" default.
    base_dir = Path("out/matrix_runs/war")
    
    if not base_dir.exists():
        st.warning("No Matrix Runs found. (Is Cloud Loop running?)")
        return
        
    # Find all verdict files
    # pattern: out/matrix_runs/war/*/reports/pool_court_verdict_v1.json
    verdict_files = sorted(list(base_dir.glob("*/reports/pool_court_verdict_v1.json")), reverse=True)
    
    if not verdict_files:
        st.info("No verdicts found yet.")
        return
        
    st.write(f"Found {len(verdict_files)} verdicts.")
    
    # 2. Table Data
    data = []
    for p in verdict_files[:20]: # Show last 20
        try:
            with open(p) as f:
                verdict = json.load(f)
            
            run_id = p.parent.parent.name
            
            # Load Scorecard for details
            scorecard_path = p.parent / "pool_scorecard_v1.json"
            scorecard = {}
            if scorecard_path.exists():
                with open(scorecard_path) as f:
                    scorecard = json.load(f)
            
            # Load Risk Report for blocked reasons
            risk_path = p.parent / "pool_risk_report_v2.json"
            risk_report = {}
            if risk_path.exists():
                with open(risk_path) as f:
                    risk_report = json.load(f)
            
            timestamp = verdict.get("built_ts_iso", verdict.get("ts", "N/A"))
            v_res = verdict.get("verdict", "UNKNOWN")
            decision = verdict.get("decision_action", "UNKNOWN")
            
            # Icons
            decision_display = {
                "ALLOW": "ALLOW ✅",
                "BLOCK": "BLOCK ⛔",
                "SKIP": "SKIP 💤"
            }.get(decision, decision)

            # Format reasons
            reasons = []
            
            # From Verdict lists (Priority)
            if "blocked_reasons" in verdict:
                reasons.extend([f"BLOCK: {r}" for r in verdict["blocked_reasons"]])
            if "skipped_reasons" in verdict:
                reasons.extend([f"SKIP: {r}" for r in verdict["skipped_reasons"]])
                
            # Legacy fallback
            if not reasons:
                gates = verdict.get("gates", [])
                for g in gates:
                    if g["status"] not in ["PASS", "WARN"] and g["gate_id"] not in ["Global Cap OK"]: # filters
                         reasons.append(f"{g['gate_id']}:{g['status']}")
                
                blocked_map = risk_report.get("blocked_reasons_count", {})
                for reason, count in blocked_map.items():
                    reasons.append(f"{reason} (x{count})")
            
            # Stats
            stats = verdict.get("stats", {})
            stats_str = f"Plan: {stats.get('planned_orders', 0)}"
                
            evidence_ok = scorecard.get("evidence_ok", False)
            
            data.append({
                "Run ID": run_id,
                "Time": timestamp,
                "Decision": decision_display,
                "Verdict": v_res,
                "Reasons": ", ".join(reasons),
                "Stats": stats_str,
                "Evidence": "OK" if evidence_ok else "MISSING"
            })
            
        except Exception as e:
            st.error(f"Error reading {p}: {e}")
            
    st.table(data)
    
    # 3. Detail View
    st.subheader("Latest Run Details")
    if verdict_files:
         latest = verdict_files[0]
         st.text(f"Source: {latest}")
         with open(latest) as f:
             st.json(json.load(f))
