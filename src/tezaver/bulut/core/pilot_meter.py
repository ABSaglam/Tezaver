# Tezaver Bulut - Pilot Meter (P5/P6)
"""
Tracks 24h USDT limit for mainnet pilot phase.
P6: Limit now comes from ExpansionPolicy tier (50/200/500).
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


class PilotMeter:
    """
    Tracks mainnet pilot phase spending limit.
    
    P5: Constitution v0.28 - 24h window limit tracking.
    P6: Limit is dynamic based on expansion tier.
    """
    
    PILOT_WINDOW_HOURS = 24
    DEFAULT_LIMIT_USDT = 50.0  # Fallback if no expansion policy
    
    def __init__(self, persistence, expansion_policy=None):
        self._persistence = persistence
        self._expansion_policy = expansion_policy
        self._cache: Optional[Dict] = None
    
    def _get_limit(self) -> float:
        """Get current limit from expansion policy or default."""
        if self._expansion_policy:
            try:
                return self._expansion_policy.get_tier_limit()
            except Exception:
                pass
        return self.DEFAULT_LIMIT_USDT
    
    def _load_state(self) -> Dict:
        """Load pilot state from persistence."""
        if self._cache:
            return self._cache
            
        state = self._persistence.get_pilot_state()
        if not state:
            state = {
                "start_ts": None,
                "committed_usdt": 0.0,
                "last_commit_ts": None
            }
        self._cache = state
        return state
    
    def _save_state(self, state: Dict):
        """Save pilot state to persistence."""
        self._persistence.update_pilot_state(state)
        self._cache = state
    
    def get_status(self) -> Dict[str, Any]:
        """Get current pilot meter status."""
        state = self._load_state()
        limit = self._get_limit()
        
        start_ts = state.get("start_ts")
        committed = state.get("committed_usdt", 0.0)
        
        now = datetime.now(timezone.utc)
        
        # Calculate window
        if start_ts:
            start_dt = datetime.fromisoformat(start_ts)
            end_dt = start_dt + timedelta(hours=self.PILOT_WINDOW_HOURS)
            time_left_seconds = max(0, (end_dt - now).total_seconds())
            active = now < end_dt
        else:
            start_dt = None
            end_dt = None
            time_left_seconds = self.PILOT_WINDOW_HOURS * 3600
            active = False
        
        remaining = max(0.0, limit - committed)
        
        # Include tier info if available
        tier_info = {}
        if self._expansion_policy:
            try:
                tier = self._expansion_policy.get_current_tier()
                tier_info = {
                    "current_tier": tier.value,
                    "current_tier_name": tier.name
                }
            except Exception:
                pass
        
        return {
            "active": active,
            "start_ts": start_ts,
            "end_ts": end_dt.isoformat() if end_dt else None,
            "limit_usdt": limit,
            "committed_usdt": committed,
            "remaining_usdt": remaining,
            "time_left_seconds": time_left_seconds,
            "time_left_hours": round(time_left_seconds / 3600, 2),
            **tier_info
        }
    
    def is_limit_reached(self) -> bool:
        """Check if pilot limit has been reached."""
        status = self.get_status()
        return status["remaining_usdt"] <= 0
    
    def can_commit(self, notional_usdt: float) -> bool:
        """Check if a notional amount can be committed."""
        status = self.get_status()
        return status["remaining_usdt"] >= notional_usdt
    
    def commit_notional(self, notional_usdt: float) -> bool:
        """
        Commit notional to pilot meter.
        
        Returns True if committed, False if limit would be exceeded.
        """
        if not self.can_commit(notional_usdt):
            return False
            
        state = self._load_state()
        now = datetime.now(timezone.utc)
        
        # Start pilot phase on first commit
        if not state.get("start_ts"):
            state["start_ts"] = now.isoformat()
        
        state["committed_usdt"] = state.get("committed_usdt", 0.0) + notional_usdt
        state["last_commit_ts"] = now.isoformat()
        
        self._save_state(state)
        return True
    
    def reset(self):
        """Reset pilot meter (for testing or new phase)."""
        state = {
            "start_ts": None,
            "committed_usdt": 0.0,
            "last_commit_ts": None
        }
        self._save_state(state)
        self._cache = None
