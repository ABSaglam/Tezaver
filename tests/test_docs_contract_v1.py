import pytest
from fastapi.routing import APIRoute
from tezaver.bulut.app_backend import app

# Valid tags set from requirements
VALID_TAGS = {
    "Ops", "Risk", "Perf", "Trading", "Intel", 
    "Replay", "Forensics", "Data", "Config", "Security",
    # Adding extra mapping for existing tags to allow passing or need migration
    "Health", "Ranking", "Trade", "Bars", "Daemon", "Reconcile", 
    "Positions", "Exit Profiles", "Exchange Info", "Time Sync", 
    "Income", "FX", "Environment", "Launch", "Plans", 
    "UI", "Proof Ladder", "Fault Lab", "Replay Lab", "Migrations"
}
# The user asked to "Standardize" which implies we should probably migrate old tags to new buckets.
# But for now I'll include existing ones in "allowed" but print warnings, or stick to the STRICT list?
# User said: "Tag setini sabitle: [...]. Her endpoint'i bu setten 1+ tag ile etiketle."
# So I must enforce ONLY the strict list.
STRICT_TAGS = {
    "Ops", "Risk", "Perf", "Trading", "Intel", 
    "Replay", "Forensics", "Data", "Config", "Security"
}

def test_api_docs_contract():
    """
    Enforce documentation standards for all FastAPI routes.
    """
    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    errors = []

    for route in routes:
        path = route.path
        if path.startswith("/docs") or path.startswith("/openapi"):
            continue
            
        # 1. Check Tags
        tags = set(route.tags or [])
        if not tags:
            errors.append(f"[{path}] Missing tags")
        else:
            # Check overlap with STRICT set
            if not tags.intersection(STRICT_TAGS):
                # errors.append(f"[{path}] Invalid tags {tags}. Must use one of: {STRICT_TAGS}")
                # For now, let's just warn or fail? User said "Enforce". 
                # I will allow failure to drive the refactor.
                errors.append(f"[{path}] Tags {tags} not in standard set: {STRICT_TAGS}")

        # 2. Check Summary
        if not route.summary:
            errors.append(f"[{path}] Missing summary")
            
        # 3. Check Description
        desc = route.description or ""
        if not desc:
            errors.append(f"[{path}] Missing description")
        elif len(desc) < 30:
            errors.append(f"[{path}] Description too short (<30 chars): '{desc}'")
            
        # 4. OpsAuth check for mutations
        # Assuming mutations are methods other than GET/HEAD/OPTIONS
        methods = route.methods or set()
        is_mutation = any(m in {"POST", "PUT", "DELETE", "PATCH"} for m in methods)
        
        # Exclude specific public paths if any (e.g. login?)
        # For now assume all mutations need auth
        if is_mutation:
            if "OpsAuth" not in desc:
                 errors.append(f"[{path}][{methods}] Mutation endpoint description must contain 'OpsAuth'")

    if errors:
        pytest.fail("\n".join(["API Docs Contract Failures:"] + errors[:50] + 
                              ([f"... and {len(errors)-50} more"] if len(errors) > 50 else [])))
