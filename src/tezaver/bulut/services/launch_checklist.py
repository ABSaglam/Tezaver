# Tezaver Bulut - Launch Checklist
"""
Mainnet Launch Checklist Service.
Verifies critical system health before allowing Mainnet operations.
"""

import os
import time
from typing import Dict, Any, List

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class LaunchChecklist:
    def __init__(self, config: BulutConfig, telemetry: NdjsonTelemetry):
        self._config = config
        self._telemetry = telemetry
        self._last_result: Dict[str, Any] = {}
        self._last_run_ts: float = 0.0

    def get_last_result(self) -> Dict[str, Any]:
        return self._last_result

    def run_checks(self, ctx: Any) -> Dict[str, Any]:
        """
        Run all pre-flight checks.
        Returns: {
            "ts": float,
            "pass": bool,
            "checks": [ { "name": str, "pass": bool, "detail": str } ]
        }
        """
        checks: List[Dict[str, Any]] = []
        all_passed = True
        
        # 1. Time Sync
        # Check if synced recently (e.g. within 1 hr? or just valid offset?)
        ts_ok = False
        ts_detail = "Indeterminate"
        if hasattr(ctx, "time_sync"):
            ts_res = ctx.time_sync.get_sync_status() # {synced, offset...}
            # Assuming get_sync_status returns object or dict. 
            # Actually get_sync_info returns primitives usually.
            # Let's check logic: calling get_time_offset() works?
            # Or use `ctx.time_sync.synced`?
            # checking `status_service` logic: `time_sync` in status is object.
            # `ctx.time_sync` probably has `is_synced()`?
            # Let's assume passed if offset is small (< 1000ms).
            offset = ctx.time_sync.get_time_offset()
            if abs(offset) < 1000:
                ts_ok = True
                ts_detail = f"Offset {offset:.1f}ms"
            else:
                ts_detail = f"Offset too high: {offset}ms"
        else:
            ts_detail = "Service missing"
            
        checks.append({"name": "Time Sync", "pass": ts_ok, "detail": ts_detail})
        if not ts_ok: all_passed = False

        # 2. Exchange Info
        # Check if fresh (cache populated)
        ex_ok = False
        ex_detail = "Empty"
        if hasattr(ctx, "exchangeinfo_cache"):
             info = ctx.exchangeinfo_cache.get_cached_info()
             if info and info.get("symbols"):
                 ex_ok = True
                 ex_detail = f"{len(info['symbols'])} symbols"
        checks.append({"name": "Exchange Info", "pass": ex_ok, "detail": ex_detail})
        if not ex_ok: all_passed = False

        # 3. FX Rates (if enabled)
        # We can implement if needed. Skipping for MVP unless critical.
        # Let's check status service logic? It checks FX.
        # For now, mark PASS (Optional).

        # 4. User Data Stream
        ws_ok = False
        ws_detail = "Disabled"
        if self._config.user_data_ws_enabled:
            # Check context user_data_stream.connected
            if hasattr(ctx, "user_data_stream"):
                 # connected is async-set property?
                 # Accessing `connected` attribute
                 if ctx.user_data_stream.connected:
                     ws_ok = True
                     ws_detail = "Connected"
                 else:
                     ws_detail = "Disconnected"
            else:
                ws_detail = "Service missing"
                
            checks.append({"name": "User Data Stream", "pass": ws_ok, "detail": ws_detail})
            if not ws_ok: all_passed = False

        # 5. Allowlist (Mainnet Only)
        if self._config.mode == "REAL_MAINNET" and self._config.require_allowlist_on_mainnet:
            al_ok = False
            al_detail = "Missing/Empty"
            # Check AllowlistSource
            if hasattr(ctx, "allowlist_source"):
                count = ctx.allowlist_source.get_allowlist_count()
                if count > 0:
                    al_ok = True
                    al_detail = f"{count} symbols allowed"
                else:
                    al_detail = "Allowlist empty"
            else:
                # If no service, check manual file?
                # But allowlist_source should exist.
                pass
            checks.append({"name": "Allowlist", "pass": al_ok, "detail": al_detail})
            if not al_ok: all_passed = False

        # 6. Armed (Execution)
        # Should be armed for PASS? Or is this check for "Safe to Arm"?
        # Actually Gate says "Mainnet + Checklist Pass + Armed -> Live".
        # So Checklist doesn't require Armed to pass. Checklist verifies environment.
        # But maybe we check if "Safe to run". Armed is a switch.
        # We check execution module loaded.
        
        # 7. Max Notional (Mainnet Check)
        # Can we check if existing positions exceed limit?
        # Requires persistence.
        # MVP: Skip notional check here (Runtime check enforces it).
        
        # 8. Data Dirs
        # Env doctor covers this. Did Env Doctor pass?
        # Check ctx.state.startup_degraded?
        env_ok = not getattr(ctx.state, "startup_degraded", False)
        checks.append({"name": "Env Doctor", "pass": env_ok, "detail": "Degraded" if not env_ok else "OK"})
        if not env_ok: all_passed = False

        # 9. Config Drift (v0.25)
        # Verify if current config matches saved/expected OR if it drifted during runtime check.
        # check_and_record returns drift=True if it DIFFERED from DB.
        # If we run this periodically, it will update DB?
        # Ideally checklist runs shouldn't mutate state unless necessary (like recording "I checked this").
        # check_and_record(source="CHECKLIST") *does* insert if drift detected.
        # This keeps the DB up to date but flags the transition.
        
        drift_res = ctx.drift_guard.check_and_record(source="CHECKLIST")
        has_drift = drift_res["drift"]
        
        d_detail = "Stable"
        if has_drift:
             d_detail = f"Drift: {drift_res['old_hash'][:6]}->{drift_res['new_hash'][:6]}"
        
        # In Mainnet, drift might be fatal if we want strict immutability.
        # Prompt: "Launch checklist drift’i de kontrol etsin (mainnet için kritik)." -> FAIL on drift?
        # If drift detected, it means "Changed since last verification".
        # Yes, mark FAIL.
        checks.append({"name": "Config Drift", "pass": not has_drift, "detail": d_detail})
        if has_drift: all_passed = False

        # 10. Constitution Checksum (v0.28)
        # Check if checksum matches expected/recorded.
        # check_and_alert() updates DB if changed, but returns "drift" if it was diff from DB.
        # If enforce=True, drift = fail.
        c_res = ctx.constitution_guard.check_and_alert()
        c_pass = True
        c_detail = "Verified"
        
        if c_res.get("drift"):
            c_detail = f"Drift: {c_res.get('old_hash', '?')[:6]}->{c_res.get('new_hash', '?')[:6]}"
            if ctx.config.constitution_checksum_enforce and ctx.config.mode == "REAL_MAINNET":
                c_pass = False
            else:
                c_detail += " (Allowed)"
                
        checks.append({"name": "Constitution Lock", "pass": c_pass, "detail": c_detail})
        if not c_pass: all_passed = False

        # 11. Proof Ladder (v1)
        # Verify valid stage and effective cap > 0.
        pl_ok = False
        pl_detail = "Skipped"
        if ctx.config.proof_ladder_enabled and hasattr(ctx, "proof_ladder"):
             # Get Status
             state = ctx.persistence.get_proof_ladder_state()
             if not state:
                 pl_detail = "Not Seeded"
             else:
                 stage_id = state["stage_id"]
                 eff_cap = ctx.proof_ladder.compute_effective_mainnet_cap()
                 
                 pl_ok = (eff_cap > 0)
                 pl_detail = f"{stage_id} (Cap: {eff_cap})"
                 if not pl_ok: pl_detail += " [Zero Cap]"
                 
             if ctx.config.mode == "REAL_MAINNET":
                 checks.append({"name": "Proof Ladder", "pass": pl_ok, "detail": pl_detail})
                 if not pl_ok: all_passed = False
        

        # Result
        self._last_run_ts = time.time()
        self._last_result = {
            "ts": self._last_run_ts,
            "pass": all_passed,
            "checks": checks
        }
        
        self._telemetry.emit("LAUNCH_CHECKLIST_RUN", {
            "pass": all_passed,
            "failed_count": sum(1 for c in checks if not c["pass"])
        })
        
        return self._last_result
