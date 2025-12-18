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
        
    def check_entry_allowed(self, symbol: str, notional: float, cycle_ts: float) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if entry is allowed for symbol.
        Returns (is_allowed, reason_code, details).
        """
        # 1. Daily Loss Guard
        today_pnl = self._db.get_today_net_pnl()
        limit = -abs(self._config.daily_loss_limit_usdt)
        
        if self._config.entry_halted_on_daily_loss and today_pnl <= limit:
            return False, "DAILY_LOSS_GUARD", {
                "today_pnl": today_pnl, 
                "limit": limit
            }
            
        # 2. Cooldown after SL
        # Get last position status (even if closed)
        pos = self._db.get_position(symbol)
        if pos and pos.get("status") == "CLOSED":
            reason = pos.get("last_exit_reason")
            exit_ts_str = pos.get("last_exit_ts")
            
            if reason == "SL" and exit_ts_str:
                # Convert ISO back to timestamp
                try:
                    dt = datetime.fromisoformat(exit_ts_str)
                    exit_ts = dt.timestamp()
                    
                    # Cycle duration (approx base_tf)
                    # Assuming 15m = 900s
                    cycle_duration = 900 # Hardcoded or parse config base_tf?
                    # Cooldown duration
                    cooldown_s = self._config.cooldown_cycles_after_sl * cycle_duration
                    
                    elapsed = cycle_ts - exit_ts
                    if elapsed < cooldown_s:
                        remaining_cycles = (cooldown_s - elapsed) / cycle_duration
                        return False, "COOLDOWN_AFTER_SL", {
                            "last_exit": reason,
                            "elapsed_s": int(elapsed),
                            "required_s": int(cooldown_s),
                            "remaining_cycles": round(remaining_cycles, 1)
                        }
                except Exception as e:
                    print(f"[RISK] Error parsing last_exit_ts {exit_ts_str}: {e}")
                    
        # 3. Group Caps
        group = self._groups.get_group(symbol)
        cap = self._groups.get_cap(group)
        
        # Count open in group
        open_positions = self._db.get_open_positions()
        group_count = 0
        for p in open_positions:
            s_sym = p["symbol"]
            if self._groups.get_group(s_sym) == group:
                group_count += 1
                
        if group_count >= cap:
            return False, "GROUP_CAP_REACHED", {
                "group": group,
                "count": group_count,
                "cap": cap
            }
            
        # 4. Global Limits
        global_cap = self._config.max_open_positions
        if len(open_positions) >= global_cap:
             return False, "MAX_POSITIONS_REACHED", {"count": len(open_positions), "cap": global_cap}

        return True, "ALLOWED", {}
        
    def get_risk_status(self) -> Dict[str, Any]:
        """Get summary status for UI."""
        today_pnl = self._db.get_today_net_pnl()
        loss_limit = -abs(self._config.daily_loss_limit_usdt)
        halted = self._config.entry_halted_on_daily_loss and today_pnl <= loss_limit
        
        # Calculate group usage?
        # Expensive to scan all?
        # Maybe just summary of open count
        open_count = self._db.get_open_position_count()
        
        return {
            "today_pnl": today_pnl,
            "daily_loss_limit": loss_limit,
            "entry_halted": halted,
            "open_positions": open_count,
            "max_positions": self._config.max_open_positions
        }
