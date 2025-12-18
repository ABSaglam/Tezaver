# Tezaver Bulut - Safety Guard
"""
Safety Guard service to block unauthorized executions.
"""

from typing import Tuple, Optional, Any
import time

# We pass "ctx" as Any to avoid circular imports, or just pass config/state components.
# Here we take the BulutContext-like object or specific config/state.

class SafetyGuard:
    """
    Blocks execution if critical safety conditions are not met.
    """
    
    @staticmethod    
    def check_trade_lock(ctx: Any) -> Tuple[bool, Optional[str]]:
        """
        Check if trading implies "LOCKED".
        Returns (locked: bool, reason: str).
        """
        # 0. Startup Degraded (Env Doctor)
        if getattr(ctx.state, "startup_degraded", False):
            return True, "STARTUP_SELFTEST_FAIL"

        # v0.24 Mainnet Launch Gate
        is_mainnet = (ctx.config.mode == "REAL_MAINNET")
        
        if is_mainnet:
            # 1. Allowlist Mandatory
            if ctx.config.require_allowlist_on_mainnet:
                # Check if allowlist has entries
                # We can access allowlist_source if available
                if hasattr(ctx, "allowlist_source"):
                    if ctx.allowlist_source.get_allowlist_count() == 0:
                        return True, "MAINNET_ALLOWLIST_MISSING"
                else:
                    return True, "MAINNET_ALLOWLIST_SERVICE_MISSING"

            # 2. Launch Checklist Mandatory
            if ctx.config.mainnet_require_checklist_pass:
                # Check last result
                checklist = ctx.launch_checklist.get_last_result()
                if not checklist.get("pass"):
                    return True, "CHECKLIST_NOT_PASSING"
                
                # Check Age
                age = time.time() - checklist.get("ts", 0)
                if age > ctx.config.checklist_max_age_seconds:
                    return True, "CHECKLIST_STALE"

        # 1. Pattern Pack Loaded?
        if not ctx.state.pattern_pack_loaded:
            return True, "PATTERN_PACK_NOT_LOADED"

        # 2. Risk Halted? (from PortfolioRisk) - if applicable
        # (PortfolioRisk usually handles position limits, but global halt?)
        # Ignoring for now unless explicit halt flag exists.

        return False, None  
    
    @staticmethod
    def check_execution_allowed(ctx: Any) -> Tuple[bool, Optional[str]]:
        """
        Check if execution is allowed.
        Returns: (allowed, blocking_reason)
        """
        config = ctx.config
        state = ctx.state
        
        # 1. Main Toggle
        if not config.execution_enabled:
            return False, "EXECUTION_DISABLED"
            
        # 2. ARM Token (Two-man rule / secure deployment)
        if config.require_arm:
            if not config.arm_token:
                return False, "ARM_TOKEN_MISSING"
                
            # If we wanted to validate token content (e.g. hash match), do it here.
            # For v0.06 just presence is enough.
        
        # 3. Mode
        if config.mode != "REAL_TESTNET":
            # Safety first: block MAINNET by default in v0.06
            return False, f"MODE_BLOCK_{config.mode}"
            
        # 4. Pattern Pack (Intelligence Source)
        if not state.pattern_pack_loaded:
            return False, "PATTERN_PACK_MISSING"
        
        # 5. Trade Lock (System-wide lock managed by context)
        # Context manages trade_locked, but usually due to pattern pack.
        # Check explicitly just to be safe if other reasons exist.
        if state.trade_locked:
             return False, f"SYSTEM_LOCKED_{state.trade_lock_reason}"
             
        # 6. Time Sync Check (v0.13)
        if config.block_execution_if_time_sync_fail:
            # Need to access time_sync from ctx.
            # ctx has it as lazy property.
            if hasattr(ctx, "time_sync") and ctx.time_sync:
                healthy, _ = ctx.time_sync.is_healthy()
                if not healthy:
                    return False, "TIME_SYNC_UNHEALTHY"
        
        return True, None
