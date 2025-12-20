from typing import Protocol, List, Dict, Any

class NotifierPort(Protocol):
    def emit_alert(self, alert: Dict[str, Any]) -> None:
        """
        Emits an alert. Implementation should handle persistence and idempotency.
        """
        ...

    def list_active(self) -> List[Dict[str, Any]]:
        """
        Returns a list of active alerts.
        """
        ...

    def ack(self, alert_id: str) -> None:
        """
        Acknowledges an alert, moving it to history.
        """
        ...
