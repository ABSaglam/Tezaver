# Tezaver Bulut - Ops Auth Logic
"""
Middleware logic for Ops Auth Gate.
Validates mutation requests against configured secret token.
"""

from fastapi import Request, HTTPException, status
from tezaver.bulut.core.config import BulutConfig

def is_mutation(request: Request) -> bool:
    """Check if request is a state-changing operation."""
    return request.method in ["POST", "PUT", "PATCH", "DELETE"]

async def check_ops_auth(request: Request, config: BulutConfig):
    """
    Enforce Ops Auth Gate.
    Raises HTTPException if unauthorized.
    """
    if not config.ops_auth_enabled:
        return

    # Check if mutation
    if is_mutation(request):
        # Allow Read-Only?
        # If enabled, GET is allowed without check. 
        # But this function only cares about authorization.
        # If it IS a mutation, we MUST check.
        
        expected_token = config.ops_auth_token_env
        if not expected_token:
            # Security Risk: Enabled but no token set?
            # Fail closed or Open? 
            # If enabled and no token => Block all mutations to be safe.
            print(f"[OpsAuth] CRITICAL: OPS_AUTH_ENABLED but TEZAVER_OPS_TOKEN not set. Blocking mutations.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail="Ops Auth enabled but token not configured."
            )

        client_token = request.headers.get(config.ops_auth_header)
        
        if client_token != expected_token:
            # Deny
            # Telemetry hook needed here? Ideally yes, but ctx not easily avail in simple middleware func
            # We rely on caller or just log.
            print(f"[OpsAuth] DENIED: {request.method} {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or Invalid Ops Token. Read-only mode active."
            )
    
    # If not mutation (GET), we allow if readonly_allow is True.
    # What if readonly_allow is False? (Private system)
    # Then we must check token for GET too.
    elif not config.ops_auth_readonly_allow:
         expected_token = config.ops_auth_token_env
         client_token = request.headers.get(config.ops_auth_header)
         if client_token != expected_token:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="System Locked. Ops Token required for access."
            )
