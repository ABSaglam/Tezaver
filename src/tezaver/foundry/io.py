"""
Foundry I/O Layer
=================

Write QC reports and summaries to disk.
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime
from collections import Counter

from tezaver.foundry.models import QCReport


def write_qc_report(report: QCReport, base_dir: str = ".tezaver_matrix/foundry") -> str:
    """
    Write individual QC report to JSON file.
    
    Path: {base_dir}/qc_reports/{symbol}/{tf}/qc_{event_id}.json
    
    Args:
        report: QCReport to write
        base_dir: Base directory for foundry outputs
    
    Returns:
        Path to written file
    """
    # Create directory structure
    report_dir = Path(base_dir) / "qc_reports" / report.symbol / report.timeframe
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # Write report
    report_file = report_dir / f"qc_{report.event_id}.json"
    with open(report_file, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    
    return str(report_file)


def write_qc_summary(reports: List[QCReport], date: str = None, base_dir: str = ".tezaver_matrix/foundry") -> str:
    """
    Write summary report in markdown format.
    
    Path: {base_dir}/qc_reports/summary_{YYYYMMDD}.md
    
    Args:
        reports: List of QCReports  to summarize
        date: Date string (YYYYMMDD), defaults to today
        base_dir: Base directory for foundry outputs
    
    Returns:
        Path to written summary
    """
    if date is None:
        date = datetime.utcnow().strftime("%Y%m%d")
    
    # Calculate stats
    total = len(reports)
    passed = sum(1 for r in reports if r.qc_verdict == "PASS")
    failed = total - passed
    
    # Count fail reasons
    fail_counter = Counter()
    warn_counter = Counter()
    
    for report in reports:
        for fail in report.fails:
            fail_counter[fail] += 1
        for warn in report.warns:
            warn_counter[warn] += 1
    
    # Top reasons
    top_fails = fail_counter.most_common(5)
    top_warns = warn_counter.most_common(5)
    
    # Average score
    avg_score = sum(r.score for r in reports) / total if total > 0 else 0
    
    # Write summary
    summary_dir = Path(base_dir) / "qc_reports"
    summary_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = summary_dir / f"summary_{date}.md"
    
    with open(summary_file, 'w') as f:
        f.write(f"# QC Gate Summary - {date}\n\n")
        f.write(f"**Generated:** {datetime.utcnow().isoformat()}\n\n")
        f.write("---\n\n")
        
        f.write("## Overall Stats\n\n")
        f.write(f"- **Total Annotations:** {total}\n")
        f.write(f"- **PASS:** {passed} ({passed/total*100:.1f}%)\n")
        f.write(f"- **FAIL:** {failed} ({failed/total*100:.1f}%)\n")
        f.write(f"- **Average Score:** {avg_score:.1f}/100\n\n")
        
        f.write("---\n\n")
        
        f.write("## Top Fail Reasons\n\n")
        if top_fails:
            for reason, count in top_fails:
                f.write(f"- **{reason}:** {count} ({count/total*100:.1f}%)\n")
        else:
            f.write("*No failures recorded*\n")
        f.write("\n")
        
        f.write("---\n\n")
        
        f.write("## Top Warn Reasons\n\n")
        if top_warns:
            for reason, count in top_warns:
                f.write(f"- **{reason}:** {count} ({count/total*100:.1f}%)\n")
        else:
            f.write("*No warnings recorded*\n")
        f.write("\n")
        
        f.write("---\n\n")
        
        f.write("## By Symbol/Timeframe\n\n")
        # Group by symbol/timeframe
        by_sym_tf = {}
        for report in reports:
            key = f"{report.symbol}/{report.timeframe}"
            if key not in by_sym_tf:
                by_sym_tf[key] = {"pass": 0, "fail": 0}
            if report.qc_verdict == "PASS":
                by_sym_tf[key]["pass"] += 1
            else:
                by_sym_tf[key]["fail"] += 1
        
        f.write("| Symbol/TF | PASS | FAIL | Total |\n")
        f.write("|-----------|------|------|-------|\n")
        for key in sorted(by_sym_tf.keys()):
            stats = by_sym_tf[key]
            total_key = stats["pass"] + stats["fail"]
            f.write(f"| {key} | {stats['pass']} | {stats['fail']} | {total_key} |\n")
        f.write("\n")
    
    return str(summary_file)


def write_qc_batch(reports: List[QCReport], base_dir: str = ".tezaver_matrix/foundry") -> dict:
    """
    Write a batch of QC reports (individual + summary).
    
    Args:
        reports: List of QCReports
        base_dir: Base directory
    
    Returns:
        Dict with written file paths
    """
    result = {
        "individual_reports": [],
        "summary_report": None
    }
    
    # Write individual reports
    for report in reports:
        report_path = write_qc_report(report, base_dir)
        result["individual_reports"].append(report_path)
    
    # Write summary
    if reports:
        summary_path = write_qc_summary(reports, base_dir=base_dir)
        result["summary_report"] = summary_path
    
    return result
