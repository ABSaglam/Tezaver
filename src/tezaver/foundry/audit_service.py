"""
Foundry Audit Service
=====================

Manages the "Audit Log" (Karar Defteri Tutanakları).
Appends immutable logs to `foundry_audit.jsonl`.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

AUDIT_LOG_PATH = Path(".tezaver_matrix/foundry/foundry_audit.jsonl")

class AuditService:
    def __init__(self, log_path: Path = AUDIT_LOG_PATH):
        self.log_path = log_path
        self._ensure_dir()

    def _ensure_dir(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(
        self, 
        action: str, 
        subject: str, 
        verdict: str, 
        details: Dict[str, Any], 
        policy_version: str = "Unknown"
    ):
        """
        Log a decision to the audit trail.
        
        Args:
            action: E.g., "QC_EVAL", "PACKAGE_CREATE"
            subject: Unique ID (e.g., BTC_15m_...)
            verdict: "PASS", "FAIL", "SUCCESS", "ERROR"
            details: Contextual info (score, path, failure reason)
            policy_version: Version of the policy enforced
        """
        entry = {
            "ts": datetime.now().isoformat(),
            "action": action,
            "subject": subject,
            "verdict": verdict,
            "details": details,
            "policy_ver": policy_version
        }
        
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Fallback for critical logging failure
            print(f"[CRITICAL] Failed to write to audit log: {e}")

    def read_recent_logs(self, limit: int = 50) -> list:
        """Read the tail of the audit log."""
        if not self.log_path.exists():
            return []
            
        lines = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                # Naive read all for simplicity (optimize later for huge files)
                lines = f.readlines()
            
            # Parse last N lines reversed
            entries = []
            for line in reversed(lines[-limit:]):
                try:
                    entries.append(json.loads(line))
                except: pass
            return entries
        except:
            return []
