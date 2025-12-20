def parse_timeframe_to_seconds(tf: str) -> int:
    """Parses standard timeframe strings to seconds."""
    if tf == "15m":
        return 900
    if tf == "1h":
        return 3600
    if tf == "4h":
        return 14400
    raise ValueError(f"Unsupported timeframe: {tf}")
