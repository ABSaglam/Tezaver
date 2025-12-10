"""
Tezaver Matrix Experiments
==========================

Matrix integration experiments and War Game simulations.
"""

from typing import Dict, Any
from dataclasses import asdict

from tezaver.sim.sim_profile_registry import (
    load_matrix_candidate_profiles,
    export_btc_silver_core_profiles_to_matrix,
    MatrixCandidateProfile,
)


def _format_capital_line(metrics: Dict[str, Any]) -> str:
    """Format 100 → X capital line from metrics."""
    cs = metrics.get("capital_start", 100.0)
    ce = metrics.get("capital_end", cs)
    return f"100 → {ce:.2f}"


def run_btc_silver_core_matrix_report(
    include_4h_experimental: bool = False
) -> Dict[str, Any]:
    """
    Export BTC Silver core profiles and generate Matrix report.
    
    1) Export 15m, 1h [+ optional 4h] profiles to Matrix candidates
    2) Load back and create summary report
    
    This is the first step of Matrix integration - verifying profiles
    are correctly exported with 100 → X metrics.
    """
    # 1) Export profiles
    export_result = export_btc_silver_core_profiles_to_matrix(
        include_4h_experimental=include_4h_experimental
    )

    # 2) Load back from Matrix storage
    profiles = load_matrix_candidate_profiles()

    # 3) Target profile IDs
    target_ids = [
        "BTC_SILVER_15M_CORE_V1",
        "BTC_SILVER_1H_CORE_V1",
    ]
    if include_4h_experimental:
        target_ids.append("BTC_SILVER_4H_CORE_V0_EXPERIMENTAL")

    report: Dict[str, Any] = {
        "profiles": {},
        "export_result": export_result,
    }

    for pid in target_ids:
        p = profiles.get(pid)
        if p is None:
            report["profiles"][pid] = {
                "ok": False,
                "reason": "profile_not_found",
            }
            continue

        metrics = p.metrics
        capital_line = _format_capital_line(metrics)

        report["profiles"][pid] = {
            "ok": True,
            "symbol": p.symbol,
            "timeframe": p.timeframe,
            "strategy_type": p.strategy_type,
            "capital_line": capital_line,
            "metrics": metrics,
        }

    return report


def print_matrix_report(report: Dict[str, Any]) -> None:
    """Pretty print Matrix report to console."""
    print("=" * 60)
    print("BTC Silver Core – Matrix Candidate Report")
    print("=" * 60)
    print()
    
    for pid, info in report["profiles"].items():
        if not info["ok"]:
            print(f"❌ {pid}: NOT OK – {info.get('reason')}")
            continue
        
        metrics = info["metrics"]
        print(f"✅ {pid}")
        print(f"   Symbol:    {info['symbol']}")
        print(f"   Timeframe: {info['timeframe']}")
        print(f"   Type:      {info['strategy_type']}")
        print(f"   Capital:   {info['capital_line']}")
        print(f"   Trades:    {metrics.get('trade_count', 0)}")
        print(f"   Win Rate:  {metrics.get('win_rate', 0)*100:.1f}%")
        print()


if __name__ == "__main__":
    import sys
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"

    if cmd == "report":
        # Default: 15m + 1h only
        result = run_btc_silver_core_matrix_report(include_4h_experimental=False)
        print_matrix_report(result)

    elif cmd == "report_with_4h":
        # Include 4h experimental
        result = run_btc_silver_core_matrix_report(include_4h_experimental=True)
        print_matrix_report(result)

    else:
        print(f"Unknown command: {cmd}")
        print("Usage:")
        print("  python -m tezaver.matrix.matrix_experiments report")
        print("  python -m tezaver.matrix.matrix_experiments report_with_4h")
