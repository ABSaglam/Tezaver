"""
Preflight Mode - System Readiness Checks
"""

import os
import sys
import time
import shutil
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Decision Enum
PASS = "PASS"
WARN = "WARN"
BLOCK = "BLOCK"

@dataclass
class PreflightContext:
    """Context for preflight checks including config and runtime args."""
    args: Any  # argparse Namespace
    config: Any  # LiveLoopConfig
    symbols: List[str]
    timeframe: str
    telemetry_path: Path = Path("data/logs/live_events.ndjson")
    secrets_path: Path = Path("data/secrets/live_keys.txt")

@dataclass
class CheckResult:
    """Result of a single check."""
    name: str
    status: str  # PASS, WARN, BLOCK
    message: str
    metric: Optional[float] = None

@dataclass
class PreflightResult:
    """Overall preflight result."""
    decision: str  # PASS, WARN, BLOCK
    checks: List[CheckResult]
    summary: str

def check_config_sanity(ctx: PreflightContext) -> CheckResult:
    """Check for obviously invalid configuration."""
    if not ctx.symbols:
        return CheckResult("config_sanity", BLOCK, "No symbols provided")
    
    if not ctx.timeframe:
        return CheckResult("config_sanity", BLOCK, "No timeframe provided")
        
    if ctx.config.poll_interval_sec <= 0:
        return CheckResult("config_sanity", BLOCK, f"Invalid poll interval: {ctx.config.poll_interval_sec}")
        
    return CheckResult("config_sanity", PASS, "Config seems valid")

def check_telemetry_writable(ctx: PreflightContext) -> CheckResult:
    """Check if telemetry file is writable."""
    try:
        ctx.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ctx.telemetry_path, "a") as f:
            pass  # touch
        return CheckResult("telemetry_writable", PASS, f"Writable: {ctx.telemetry_path}")
    except Exception as e:
        return CheckResult("telemetry_writable", BLOCK, f"Cannot write to {ctx.telemetry_path}: {e}")

def check_clock_sanity(ctx: PreflightContext) -> CheckResult:
    """Check if system clock is reasonable."""
    now = datetime.now(timezone.utc)
    # Check if year is reasonable (e.g. >= 2025)
    if now.year < 2025:
         return CheckResult("clock_sanity", WARN, f"System year {now.year} seems old (< 2025)")
    return CheckResult("clock_sanity", PASS, f"Clock OK: {now.isoformat()}")

def check_exchange_mode(ctx: PreflightContext) -> CheckResult:
    """Check exchange connection/keys if REAL mode."""
    mode = getattr(ctx.args, "exchange_mode", "DRY_RUN")
    enabled = getattr(ctx.args, "exchange_enabled", False)
    
    if "REAL" in mode and enabled:
        # Check if secrets file exists or ENV vars are set
        # This is a shallow check for v1
        has_env = os.environ.get("BINANCE_API_KEY") or os.environ.get("API_KEY")
        has_file = ctx.secrets_path.exists()
        
        if not has_env and not has_file:
             return CheckResult("exchange_mode", BLOCK, f"Mode {mode} requires keys but none found (env/file)")
        return CheckResult("exchange_mode", PASS, f"Keys present for {mode}")
        
    return CheckResult("exchange_mode", PASS, f"Skip check (mode={mode})")

def check_card_availability(ctx: PreflightContext) -> CheckResult:
    """Check if strategy card exists if needed."""
    # Check args for card requirements
    open_rule = getattr(ctx.args, "open_rule_mode", "ALWAYS_OFF")
    
    if "CARD" in open_rule:
        missing = []
        for sym in ctx.symbols:
            # Check default path
            path = Path(f"data/coin_profiles/{sym}/{ctx.timeframe}/sniper_strategy_card_v1.json")
            if not path.exists():
                missing.append(f"{sym}/{ctx.timeframe}")
        
        if missing:
            return CheckResult("card_availability", BLOCK, f"Missing cards for: {', '.join(missing)}")
        return CheckResult("card_availability", PASS, "All required cards found")
        
    return CheckResult("card_availability", PASS, "Not required by mode")

def check_disk_free(ctx: PreflightContext) -> CheckResult:
    """Check free disk space."""
    try:
        total, used, free = shutil.disk_usage(".")
        free_mb = free / (1024 * 1024)
        if free_mb < 500:
            return CheckResult("disk_free", WARN, f"Low disk space: {free_mb:.0f} MB", metric=free_mb)
        return CheckResult("disk_free", PASS, f"Disk space OK: {free_mb:.0f} MB", metric=free_mb)
    except Exception as e:
         return CheckResult("disk_free", WARN, f"Could not check disk: {e}")

def run_preflight(ctx: PreflightContext, enforce_mode: str = "WARN") -> PreflightResult:
    """Run all preflight checks and return result."""
    
    check_funcs = [
        check_config_sanity,
        check_telemetry_writable,
        check_clock_sanity,
        check_exchange_mode,
        check_card_availability,
        check_disk_free
    ]
    
    results = []
    final_decision = PASS
    
    print("\n[PREFLIGHT] Running checks...")
    
    for func in check_funcs:
        res = func(ctx)
        results.append(res)
        
        # Log to console
        icon = "✅"
        if res.status == WARN: icon = "⚠️"
        if res.status == BLOCK: icon = "⛔"
        print(f"{icon} [{res.name}] {res.status}: {res.message}")
        
        # Update final decision
        if res.status == BLOCK:
            final_decision = BLOCK
        elif res.status == WARN and final_decision != BLOCK:
            final_decision = WARN
            
    # Apply enforce mode logic
    # If enforce_mode is WARN, we downgrade BLOCK -> WARN for the final exit decision?
    # Requirement: "If decision=BLOCK -> exit BEFORE starting loop with exit code 2"
    # "CLI: --preflight-enforce {WARN,BLOCK} (default WARN)"
    # Usually this means if enforce=WARN, we treat BLOCK checks as warnings? 
    # OR it means if result is BLOCK/WARN, do we block?
    # Let's interpret: 
    # If generic checks fail with BLOCK, strict mode = exit 2.
    # But usually 'enforce' refers to whether we stop on failure.
    # Preflight logic:
    # decision depends on check results.
    # effective_action depends on decision AND enforce_mode.
    # But request says: "If decision=BLOCK -> exit... If warning -> continue".
    # And "--preflight-enforce... default WARN".
    # Likely means if enforce=WARN, even a BLOCK result serves as a warning (doesn't exit).
    # Let's clarify: if enforce=BLOCK, any failure stops the show? No, check status is intrinsic severity.
    # Re-reading: "If decision=BLOCK -> exit... If decision=WARN -> continue".
    # This implies decision is FINAL derived from checks.
    # What does --preflight-enforce do?
    # Maybe: Downgrades BLOCK findings to WARN if enforce=WARN?
    # Let's assume: 
    # If enforce=BLOCK: BLOCK checks cause exit.
    # If enforce=WARN: BLOCK checks are treated as WARN (print but don't exit).
    
    if enforce_mode == "WARN" and final_decision == BLOCK:
        print("[PREFLIGHT] Enforce=WARN override: Downgrading BLOCK to WARN.")
        final_decision = WARN
        
    summary = f"Preflight finished: {final_decision}"
    print(f"[PREFLIGHT] {summary}\n")
    
    # Emit Telemetry
    emit_preflight_telemetry(ctx, final_decision, results)
    
    return PreflightResult(final_decision, results, summary)

def emit_preflight_telemetry(ctx: PreflightContext, decision: str, results: List[CheckResult]):
    """Emit PREFLIGHT_EVAL event."""
    # Redact message if needed? Usually generic.
    
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "PREFLIGHT_EVAL",
        "scope": "GLOBAL",
        "decision": decision,
        "failed_checks": [r.name for r in results if r.status != PASS],
        "messages": [f"{r.name}:{r.status}:{r.message}" for r in results if r.status != PASS],
        "metrics": {r.name: r.metric for r in results if r.metric is not None}
    }
    
    try:
        with open(ctx.telemetry_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except:
        pass  # Preflight check likely caught this anyway check_telemetry_writable
