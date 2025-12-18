# Tezaver Bulut - Portfolio Risk Service
"""
Centralized risk entry guard.
Checks Daily Loss, Cooldown, Group Caps before allowing entry.
"""

import time
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.group_caps_loader import GroupCapsLoader
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class PortfolioRiskService:
    def __init__(
        self, 
        config: BulutConfig, 
        persistence: SqlitePersistence,
        group_caps: GroupCapsLoader,
        telemetry: NdjsonTelemetry
    ):
        self._config = config
        self._db = persistence
        self._groups = group_caps
        self._telemetry = telemetry
        
    def reload_rules(self):
        """Reload risk rules."""
        self._groups.reload_if_changed()

    def check_entry_allowed(self, symbol: str, notional: float, cycle_ts: float) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if entry is allowed for symbol.
        Returns (is_allowed, reason_code, details).
        """
        details = {}
        
        # 1. Daily Loss Guard
        today_trade_pnl = self._db.get_today_net_pnl_utc()
        
        today_income = 0.0
        if getattr(self._config, "include_income_in_daily_loss_guard", True):
             types_str = getattr(self._config, "income_sync_types", "FUNDING_FEE")
             types = [t.strip() for t in types_str.split(",") if t.strip()]
             income_stats = self._db.get_today_income_sum_utc(types=types)
             today_income = income_stats.get("TOTAL", 0.0)
             
        today_total_pnl = today_trade_pnl + today_income
        limit = -abs(self._config.daily_loss_limit_usdt)
        
        if self._config.entry_halted_on_daily_loss and today_total_pnl <= limit:
            details = {
                "today_trade_pnl": today_trade_pnl, 
                "today_income": today_income,
                "today_total_pnl": today_total_pnl,
                "limit": limit
            }
            self._telemetry.emit_custom("RISK_GUARD_EVAL", {"symbol": symbol, "result": "BLOCK", "reason": "DAILY_LOSS_GUARD", **details})
            self._telemetry.emit_custom("RISK_GUARD_BLOCK", {"symbol": symbol, "reason": "DAILY_LOSS_GUARD", "details": details})
            return False, "DAILY_LOSS_GUARD", details
            
        # 2. Cooldown after SL
        pos = self._db.get_position(symbol)
        if pos and pos.get("status") == "CLOSED":
            reason = pos.get("last_exit_reason")
            exit_ts_str = pos.get("last_exit_cycle_ts")
            
            if reason == "SL" and exit_ts_str:
                try:
                    dt_exit = datetime.fromisoformat(exit_ts_str)
                    exit_ts = dt_exit.timestamp()
                    
                    cycle_duration = 900 
                    cooldown_cycles = self._config.cooldown_cycles_after_sl
                    cooldown_s = cooldown_cycles * cycle_duration
                    
                    elapsed = cycle_ts - exit_ts
                    
                    if elapsed < cooldown_s:
                        remaining_cycles = (cooldown_s - elapsed) / cycle_duration
                        details = {
                            "last_exit": reason,
                            "elapsed_s": int(elapsed),
                            "required_s": int(cooldown_s),
                            "remaining_cycles": round(remaining_cycles, 1)
                        }
                        self._telemetry.emit_custom("RISK_GUARD_EVAL", {"symbol": symbol, "result": "BLOCK", "reason": "COOLDOWN_AFTER_SL", **details})
                        self._telemetry.emit_custom("RISK_GUARD_BLOCK", {"symbol": symbol, "reason": "COOLDOWN_AFTER_SL", "details": details})
                        return False, "COOLDOWN_AFTER_SL", details
                except Exception as e:
                    print(f"[RISK] Error parsing ts {exit_ts_str}: {e}")
                    
        # 3. Group Caps
        group = self._groups.get_group(symbol)
        cap = self._groups.get_cap(group)
        
        if cap == 0:
            details = {"group": group, "cap": 0}
            self._telemetry.emit_custom("RISK_GUARD_EVAL", {"symbol": symbol, "result": "BLOCK", "reason": "GROUP_DISABLED", **details})
            self._telemetry.emit_custom("RISK_GUARD_BLOCK", {"symbol": symbol, "reason": "GROUP_DISABLED", "details": details})
            return False, "GROUP_DISABLED", details
        
        # Count open in group
        open_positions = self._db.get_open_positions()
        group_counts = self._groups.get_open_counts(open_positions)
        current_count = group_counts.get(group, 0)
        
        if current_count >= cap:
            details = {"group": group, "count": current_count, "cap": cap}
            self._telemetry.emit_custom("RISK_GUARD_EVAL", {"symbol": symbol, "result": "BLOCK", "reason": "GROUP_CAP_REACHED", **details})
            self._telemetry.emit_custom("RISK_GUARD_BLOCK", {"symbol": symbol, "reason": "GROUP_CAP_REACHED", "details": details})
            return False, "GROUP_CAP_REACHED", details
            
        # 4. Global Limits
        global_cap = self._config.max_open_positions
        if len(open_positions) >= global_cap:
             details = {"count": len(open_positions), "cap": global_cap}
             self._telemetry.emit_custom("RISK_GUARD_EVAL", {"symbol": symbol, "result": "BLOCK", "reason": "MAX_OPEN_POSITIONS", **details})
             self._telemetry.emit_custom("RISK_GUARD_BLOCK", {"symbol": symbol, "reason": "MAX_OPEN_POSITIONS", "details": details})
             return False, "MAX_OPEN_POSITIONS", details

        self._telemetry.emit_custom("RISK_GUARD_EVAL", {"symbol": symbol, "result": "ALLOWED", "reason": None})
        return True, "ALLOWED", {}
        
    def get_risk_status(self) -> Dict[str, Any]:
        """Get summary status for UI."""
        stats = self._db.get_today_pnl_stats_utc()
        today_net_pnl = stats["net_pnl"]
        
        # Income Logic
        today_income = 0.0
        income_breakdown = {}
        if getattr(self._config, "include_income_in_daily_loss_guard", True): # Or just always show it? Always show.
             types_str = getattr(self._config, "income_sync_types", "FUNDING_FEE")
             types = [t.strip() for t in types_str.split(",") if t.strip()]
             income_stats = self._db.get_today_income_sum_utc(types=types)
             today_income = income_stats.get("TOTAL", 0.0)
             income_breakdown = income_stats
             
        today_total_pnl = today_net_pnl + today_income
        
        loss_limit = -abs(self._config.daily_loss_limit_usdt)
        halted = self._config.entry_halted_on_daily_loss and today_total_pnl <= loss_limit
        
        open_positions = self._db.get_open_positions()
        group_counts = self._groups.get_open_counts(open_positions)
        
        return {
            "today_trade_net_pnl": stats["net_pnl"],
            "today_trade_gross_pnl": stats["gross_pnl"],
            "today_trade_fees": stats["fees"],
            
            "today_income": today_income,
            "today_income_breakdown": income_breakdown,
            "today_total_pnl": today_total_pnl,
            
            "daily_loss_limit": loss_limit,
            "entry_halted": halted,
            "open_positions": len(open_positions),
            "max_positions": self._config.max_open_positions,
            "group_counts": group_counts,
            "cooldown_cycles": self._config.cooldown_cycles_after_sl
        }
