# Tezaver Bulut - Alert Router (P12)
"""
Alert normalization and recommended action mapping.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class RoutedAlert:
    """Alert with routing info and recommended action."""
    id: str
    level: str  # BLOCK, WARN, INFO
    source: str
    message: str
    recommended_action: Optional[str]
    action_endpoint: Optional[str]
    timestamp: str
    context: Dict[str, Any]


# Mapping: (source, keyword) -> recommended action
ACTION_MAP = {
    # Kill switch related
    ("kill_switch", "HALTED"): ("Resume normal operations", "/kill_switch/resume"),
    ("kill_switch", "FLATTENING"): ("Monitor flatten completion", None),
    ("kill_switch", "SAFE"): ("Review and resume", "/kill_switch/resume"),
    
    # Recovery related
    ("health_check", "RECOVERY_FAILED"): ("Run recovery again", "/recovery/run"),
    ("recovery", "failed"): ("Run recovery again", "/recovery/run"),
    
    # Time sync
    ("health_check", "TIME_SYNC_SKEW"): ("Refresh time sync", "/time_sync/refresh"),
    ("time_sync", "skew"): ("Refresh time sync", "/time_sync/refresh"),
    
    # Scheduler
    ("health_check", "SCHEDULER_STALLED"): ("Restart application", None),
    ("scheduler", "stalled"): ("Restart application", None),
    
    # Exchange info
    ("exchangeinfo", "stale"): ("Refresh exchange info", "/exchangeinfo/refresh"),
    
    # Default
    ("default", "default"): ("Review alert", None),
}


class AlertRouter:
    """
    Normalizes alerts and maps to recommended actions.
    
    Takes raw alerts and enriches them with:
    - Normalized severity levels
    - Recommended actions
    - Action endpoints for UI buttons
    """
    
    def __init__(self, ctx):
        self._ctx = ctx
    
    def route_alert(self, alert: Dict[str, Any]) -> RoutedAlert:
        """Route a single alert with action mapping."""
        source = alert.get("source", "unknown")
        message = alert.get("message", "")
        level = self._normalize_level(alert.get("level", "INFO"))
        context = self._parse_context(alert.get("context_json"))
        
        # Find recommended action
        action, endpoint = self._find_action(source, message, context)
        
        return RoutedAlert(
            id=str(alert.get("id", "")),
            level=level,
            source=source,
            message=message,
            recommended_action=action,
            action_endpoint=endpoint,
            timestamp=alert.get("ts", datetime.now(timezone.utc).isoformat()),
            context=context
        )
    
    def route_alerts(self, alerts: List[Dict]) -> List[RoutedAlert]:
        """Route multiple alerts."""
        return [self.route_alert(a) for a in alerts]
    
    def _normalize_level(self, level: str) -> str:
        """Normalize alert level."""
        level = str(level).upper()
        if level in ["BLOCK", "CRITICAL", "ERROR", "SEV1"]:
            return "BLOCK"
        if level in ["WARN", "WARNING", "SEV2"]:
            return "WARN"
        return "INFO"
    
    def _parse_context(self, context_json: Optional[str]) -> Dict[str, Any]:
        """Parse context JSON."""
        if not context_json:
            return {}
        try:
            import json
            return json.loads(context_json)
        except Exception:
            return {}
    
    def _find_action(
        self, 
        source: str, 
        message: str, 
        context: Dict
    ) -> tuple[Optional[str], Optional[str]]:
        """Find recommended action for alert."""
        # Check context for pre-defined action
        if context.get("action"):
            return context.get("action"), context.get("endpoint")
        
        # Check code in context
        code = context.get("code", "")
        if code:
            for (src, keyword), (action, endpoint) in ACTION_MAP.items():
                if src in ["health_check", source] and keyword == code:
                    return action, endpoint
        
        # Search message for keywords
        message_lower = message.lower()
        for (src, keyword), (action, endpoint) in ACTION_MAP.items():
            if src == source or src == "default":
                if keyword.lower() in message_lower:
                    return action, endpoint
        
        # Default
        return None, None
    
    def get_top_alerts(self, limit: int = 20) -> List[Dict]:
        """Get top alerts with routing info."""
        try:
            raw_alerts = self._ctx.persistence.get_recent_alerts(limit=limit)
            routed = self.route_alerts(raw_alerts or [])
            
            return [
                {
                    "id": r.id,
                    "level": r.level,
                    "source": r.source,
                    "message": r.message,
                    "recommended_action": r.recommended_action,
                    "action_endpoint": r.action_endpoint,
                    "timestamp": r.timestamp
                }
                for r in routed
            ]
        except Exception:
            return []
