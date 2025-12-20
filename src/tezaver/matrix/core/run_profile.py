RUN_PROFILES = {"SNIPER", "WAR", "LIVE"}

def require_profile(p: str) -> None:
    if p not in RUN_PROFILES:
        raise ValueError(f"Invalid Run Profile: '{p}'. Allowed: {RUN_PROFILES}")
