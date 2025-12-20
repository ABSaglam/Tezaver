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
