from dataclasses import dataclass

@dataclass(frozen=True)
class Bar:
    ts: int  # timestamp in ms
    open: float
    high: float
    low: float
    close: float
    is_closed: bool

def require_closed_bar(bar: Bar) -> None:
    """Ensures the bar is explicitly marked as closed."""
    if not bar.is_closed:
        raise ValueError(f"Bar at {bar.ts} is NOT closed. Processing allowed only on closed bars.")

def require_aligned_bar_ts(bar: Bar, tf_seconds: int) -> None:
    """Ensures bar timestamp aligns with timeframe boundary."""
    if bar.ts % (tf_seconds * 1000) != 0:
        raise ValueError(f"Bar timestamp {bar.ts} not aligned to {tf_seconds}s boundary")
