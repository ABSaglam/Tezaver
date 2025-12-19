# Tezaver Bulut - Daily Ops Report Service (P12)
"""
Daily operations report with 24h metrics and summaries.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class DailyReportSummary:
    """Daily operations summary."""
    date: str
    net_pnl: float
    gross_pnl: float
    fees: float
    funding_income: float
    trades_count: int
    autopilot_minutes: int
    kill_switch_events: int
    recovery_runs: int
    allocation_peak: float
    exit_decisions: int
    alerts_count: int
    created_at: str


class DailyOpsReportService:
    """
    Generates daily operations reports with 24h metrics.
    
    Metrics:
    - PnL (net/gross), fees, funding
    - Autopilot enabled duration
    - Kill switch events
    - Recovery runs
    - Allocation peak usage
    - Exit intel decisions
    - Alerts count
    """
    
    def __init__(self, ctx):
        self._ctx = ctx
    
    def compute_today_summary(self) -> DailyReportSummary:
        """Compute today's summary from available data."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._compute_summary_for_date(today)
    
    def compute_yesterday_summary(self) -> DailyReportSummary:
        """Compute yesterday's summary."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        return self._compute_summary_for_date(yesterday)
    
    def _compute_summary_for_date(self, date: str) -> DailyReportSummary:
        """Compute summary for a specific date."""
        persistence = self._ctx.persistence
        
        # PnL metrics
        net_pnl = 0.0
        gross_pnl = 0.0
        fees = 0.0
        funding_income = 0.0
        trades_count = 0
        
        try:
            # Get income events for the day
            income_events = persistence.get_income_events_for_date(date) or []
            for event in income_events:
                income_type = event.get("income_type", "")
                amount = float(event.get("income", 0.0) or 0.0)
                
                if income_type in ["REALIZED_PNL", "COMMISSION"]:
                    gross_pnl += abs(amount)
                    net_pnl += amount
                elif income_type == "COMMISSION":
                    fees += abs(amount)
                elif income_type == "FUNDING_FEE":
                    funding_income += amount
            
            # Get trade count
            fills = persistence.get_order_fills_for_date(date) or []
            trades_count = len(fills)
        except Exception:
            pass
        
        # Autopilot minutes
        autopilot_minutes = 0
        try:
            autopilot_status = self._ctx.autopilot_service.get_status()
            if autopilot_status.get("enabled"):
                enabled_ts = autopilot_status.get("enabled_ts")
                if enabled_ts:
                    try:
                        enabled_dt = datetime.fromisoformat(enabled_ts)
                        now = datetime.now(timezone.utc)
                        autopilot_minutes = int((now - enabled_dt).total_seconds() / 60)
                    except Exception:
                        pass
        except Exception:
            pass
        
        # Kill switch events
        kill_switch_events = 0
        try:
            ks = self._ctx.kill_switch
            events = ks.get_events(limit=50)
            for e in events:
                if e.get("timestamp", "").startswith(date):
                    kill_switch_events += 1
        except Exception:
            pass
        
        # Recovery runs
        recovery_runs = 0
        try:
            reports = persistence.get_recovery_reports_for_date(date) or []
            recovery_runs = len(reports)
        except Exception:
            pass
        
        # Allocation peak
        allocation_peak = 0.0
        try:
            alloc = self._ctx.allocation_engine.get_status()
            allocation_peak = alloc.get("total_used_usdt", 0.0)
        except Exception:
            pass
        
        # Exit decisions
        exit_decisions = 0
        try:
            exit_intel = self._ctx.exit_intel_engine
            decisions = exit_intel.get_recent_decisions(limit=100)
            for d in decisions:
                if d.get("timestamp", "").startswith(date):
                    exit_decisions += 1
        except Exception:
            pass
        
        # Alerts count
        alerts_count = 0
        try:
            alerts = persistence.get_alerts_for_date(date) or []
            alerts_count = len(alerts)
        except Exception:
            pass
        
        return DailyReportSummary(
            date=date,
            net_pnl=net_pnl,
            gross_pnl=gross_pnl,
            fees=fees,
            funding_income=funding_income,
            trades_count=trades_count,
            autopilot_minutes=autopilot_minutes,
            kill_switch_events=kill_switch_events,
            recovery_runs=recovery_runs,
            allocation_peak=allocation_peak,
            exit_decisions=exit_decisions,
            alerts_count=alerts_count,
            created_at=datetime.now(timezone.utc).isoformat()
        )
    
    def save_report(self, report: DailyReportSummary) -> bool:
        """Save daily report to persistence."""
        try:
            self._ctx.persistence.save_daily_report({
                "date": report.date,
                "net_pnl": report.net_pnl,
                "gross_pnl": report.gross_pnl,
                "fees": report.fees,
                "funding_income": report.funding_income,
                "trades_count": report.trades_count,
                "autopilot_minutes": report.autopilot_minutes,
                "kill_switch_events": report.kill_switch_events,
                "recovery_runs": report.recovery_runs,
                "allocation_peak": report.allocation_peak,
                "exit_decisions": report.exit_decisions,
                "alerts_count": report.alerts_count,
                "created_at": report.created_at
            })
            return True
        except Exception:
            return False
    
    def get_report(self, date: str) -> Optional[DailyReportSummary]:
        """Get saved report for a specific date."""
        try:
            data = self._ctx.persistence.get_daily_report(date)
            if data:
                return DailyReportSummary(**data)
        except Exception:
            pass
        return None
    
    def get_today_report(self) -> Dict[str, Any]:
        """Get or compute today's report as dict."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cached = self.get_report(today)
        if cached:
            return self._summary_to_dict(cached)
        
        # Compute and return (don't save automatically)
        summary = self.compute_today_summary()
        return self._summary_to_dict(summary)
    
    def get_yesterday_report(self) -> Dict[str, Any]:
        """Get or compute yesterday's report as dict."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        cached = self.get_report(yesterday)
        if cached:
            return self._summary_to_dict(cached)
        
        # Compute and save yesterday's
        summary = self.compute_yesterday_summary()
        self.save_report(summary)
        return self._summary_to_dict(summary)
    
    def _summary_to_dict(self, summary: DailyReportSummary) -> Dict[str, Any]:
        """Convert summary to dict."""
        return {
            "date": summary.date,
            "net_pnl": summary.net_pnl,
            "gross_pnl": summary.gross_pnl,
            "fees": summary.fees,
            "funding_income": summary.funding_income,
            "trades_count": summary.trades_count,
            "autopilot_minutes": summary.autopilot_minutes,
            "kill_switch_events": summary.kill_switch_events,
            "recovery_runs": summary.recovery_runs,
            "allocation_peak": summary.allocation_peak,
            "exit_decisions": summary.exit_decisions,
            "alerts_count": summary.alerts_count,
            "created_at": summary.created_at
        }
