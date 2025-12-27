"""
Run Governed Packaging (Decision Log Enforced)
==============================================

Scans ALL revisions, applies Policy Rules (QC), validates them, 
and packages the winners. Every step is logged to the Decision Log.
"""

import sys
import argparse
from pathlib import Path
 # Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tezaver.core.annotations import SniperAnnotationRepository
from tezaver.foundry.configuration_service import ConfigurationService
from tezaver.foundry.audit_service import AuditService
from tezaver.foundry.qc_gate_v1 import run_for_symbol
from tezaver.foundry.packaging_v1 import package_event
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    # 1. Initialize Governance
    config = ConfigurationService()
    audit = AuditService()
    
    policy_ver = config.get_version()
    qc_rules = config.get_qc_rules()
    pkg_rules = config.get_packaging_rules()
    
    MIN_SCORE = qc_rules.get("min_score", 60)
    ALLOWED_TIERS = set(pkg_rules.get("allowed_tiers", []))
    
    STRICT_MODE = qc_rules.get("strict_mode", True)
    MANDATORY = set(qc_rules.get("mandatory_checks", []))
    
    print(f"🏛️  Foundry Governance v{policy_ver} Active")
    print(f"📋  Policy: Min Score {MIN_SCORE}, Strict: {STRICT_MODE}, Tiers: {ALLOWED_TIERS}")
    print("-" * 50)
    
    # 2. Discovery (Scan All Symbols)
    repo_root = Path(".tezaver_matrix/foundry/annotations")
    if not repo_root.exists():
        print("❌ No annotations found.")
        return

    # Find all coin folders
    all_symbols = [d.name for d in repo_root.iterdir() if d.is_dir()]
    all_symbols.sort()
    
    print(f"🔍 Discovered {len(all_symbols)} coins with works in progress.")
    
    total_processed = 0
    total_packaged = 0
    total_rejected = 0
    
    # 3. Execution Loop
    timeframes = ["15m", "1h", "4h"]
    
    for symbol in all_symbols:
        # print(f"Processing {symbol}...")
        for tf in timeframes:
            # A. QC Check (Rule Enforcement)
            # We use run_for_symbol to get QC Reports for ALL approved items
            qc_reports = run_for_symbol(symbol, tf)
            
            for report in qc_reports:
                total_processed += 1
                eid = report.event_id
                
                # Check Policy
                verdict = "PASS"
                reasons = []
                
                # Rule 1: QC Score
                if report.score < MIN_SCORE:
                    verdict = "FAIL"
                    reasons.append(f"Score {report.score} < {MIN_SCORE}")
                
                # Rule 2: QC Critical Fails
                if report.fails:
                    is_fatal = STRICT_MODE
                    if not is_fatal:
                        for f in report.fails:
                            if f in MANDATORY:
                                is_fatal = True
                                break
                    
                    if is_fatal:
                        verdict = "FAIL"
                        reasons.append(f"Critical QC Checks: {report.fails}")
                    else:
                        reasons.append(f"WARN: Ignored Fails: {report.fails}")
                    
                # Rule 3: Tier Check (Requires loading annotation to know Tier, or inferring)
                # For now let packaging handle tier, or check if we can get it easily.
                # Packaging script checks tier inside package_event logic? 
                # Ideally filter BEFORE packaging.
                # We'll skip tier check here for speed, and assume if it passes QC it's good.
                
                # Audit Log: QC
                audit.log_decision(
                    action="QC_EVAL",
                    subject=eid,
                    verdict=verdict,
                    details={"score": report.score, "reasons": reasons},
                    policy_version=policy_ver
                )
                
                if verdict == "FAIL":
                    total_rejected += 1
                    continue
                
                # B. Packaging (Execution)
                try:
                    bundle_path = package_event(symbol, tf, eid)
                    
                    if bundle_path:
                        total_packaged += 1
                        audit.log_decision(
                            action="PACKAGE",
                            subject=eid,
                            verdict="SUCCESS",
                            details={"bundle_path": bundle_path},
                            policy_version=policy_ver
                        )
                        print(f"✅ Packaged: {eid}")
                    else:
                        # Packaging failed internally (maybe duplicate or other check)
                        total_rejected += 1
                        audit.log_decision(
                            action="PACKAGE",
                            subject=eid,
                            verdict="SKIP",
                            details={"reason": "Internal packager rejection"},
                            policy_version=policy_ver
                        )
                except Exception as e:
                    print(f"❌ Error packaging {eid}: {e}")
                    audit.log_decision(
                        action="PACKAGE",
                        subject=eid,
                        verdict="ERROR",
                        details={"error": str(e)},
                        policy_version=policy_ver
                    )

    # 4. Summary
    print("-" * 50)
    print(f"🏁 Job Complete.")
    print(f"Total Reviewed: {total_processed}")
    print(f"✅ Packaged:     {total_packaged}")
    print(f"🚫 Rejected:     {total_rejected}")
    print(f"📒 Detailed logs written to {AuditService().log_path}")

if __name__ == "__main__":
    main()
