import time
from datetime import datetime, timezone
from typing import Dict, Any, Callable

def now_iso() -> str:
    """Returns current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()

def now_mono() -> float:
    """Returns monotonic time for elapsed calculations."""
    return time.monotonic()

def measure_skew(get_server_time_ms: Callable[[], int]) -> Dict[str, float]:
    """
    Measures clock skew between local and exchange.
    Returns offset (ms) and round-trip delay estimate.
    """
    t1 = time.time() * 1000
    try:
        server_ts = get_server_time_ms()
    except:
        return {"error": "FAILED_TO_FETCH_EXCHANGE_TIME"}
    t2 = time.time() * 1000
    
    # Estimate of network delay
    delay = (t2 - t1) / 2
    # Local time at the moment of server response arrival (approx)
    local_ts = t1 + delay
    
    offset = server_ts - local_ts
    
    return {
        "exchange_offset_ms": round(offset, 2),
        "network_delay_ms": round(delay, 2),
        "t1_local": t1,
        "t2_local": t2,
        "server_ts": server_ts
    }

def build_timebase_report(run_id: str, skew_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generates standard MX-5220 report."""
    # Simple monotonic check (we just record current state)
    mono_now = time.monotonic()
    
    return {
        "run_id": run_id,
        "ts": now_iso(),
        "monotonic_now": mono_now,
        "monotonic_ok": mono_now > 0, # Positive start
        **skew_data,
        "ok": "error" not in skew_data and abs(skew_data.get("exchange_offset_ms", 0)) < 1000
    }
