"""
Live Loop - V4 Compatible Shim

Provides tick policies and telemetry functions.
"""

TICK_POLICY_ON_CLOSED_BAR = "on_closed_bar"
TICK_POLICY_ON_ANY_NEW_BAR = "on_any_new_bar"

def emit_incident_bundle_telemetry(
    symbol: str,
    timeframe: str,
    cycle_idx: int,
    alert_level: str,
    out_path: str,
    files_count: int,
) -> None:
    """Emit telemetry event for incident bundle creation."""
    pass
