
"""
Offline Maintenance / Lab Pipeline v1 (M24)
===========================================

Orchestrates the execution of various offline analysis tasks:
- Fast15 Scans
- Time-Labs Scans (1h/4h)
- Sim Affinity & Promotion
- Rally Radar Generation

Designed to run in background or via CLI, updating system state upon completion.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
import time
import subprocess
import sys
import uuid
import logging

from tezaver.core.logging_utils import get_logger
from tezaver.core.config import get_turkey_now, DEFAULT_COINS
from tezaver.core.system_state import record_offline_maintenance_run

logger = get_logger(__name__)

# --- Data Structures ---

@dataclass
class MaintenanceTaskResult:
    name: str
    status: Literal["success", "partial", "failed", "skipped"]
    started_at: datetime
    finished_at: datetime
    duration_sec: float
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MaintenanceRunSummary:
    run_id: str
    mode: Literal["full", "fast", "symbol"]
    started_at: datetime
    finished_at: datetime
    overall_status: Literal["success", "partial", "failed"]
    tasks: List[MaintenanceTaskResult]


# --- Runner ---

class OfflineMaintenanceRunner:
    def __init__(self, mode: str = "full", symbols: Optional[List[str]] = None):
        self.mode = mode
        self.symbols = symbols if symbols else DEFAULT_COINS
        self.run_id = f"{int(time.time())}_{str(uuid.uuid4())[:8]}"
        self.tasks: List[MaintenanceTaskResult] = []
        
    def _run_subprocess(self, cmd: List[str], task_name: str) -> MaintenanceTaskResult:
        """Helper to run a CLI script as a task."""
        start_t = get_turkey_now()
        start_ts = time.time()
        
        logger.info(f"[{task_name}] Started: {' '.join(cmd)}")
        
        status = "success"
        err_msg = None
        
        # Prepare environment with PYTHONPATH
        import os
        from pathlib import Path
        
        # Assume project root is 3 levels up from this file (src/tezaver/offline)
        # Actually, let's just use the current working directory if running from project root,
        # or robustly find src.
        # Safest is to locate 'src' relative to this file.
        current_file = Path(__file__).resolve()
        src_path = current_file.parents[2] # src
        
        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH", "")
        # Add src to PYTHONPATH
        env["PYTHONPATH"] = f"{src_path}:{current_pythonpath}"
        
        try:
            # We use check=True to raise CalledProcessError on non-zero exit
            # capture_output=True to get stdout/stderr for logging if needed
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True, 
                text=True,
                env=env # Inject env
            )
            # Log stdout if needed or just keep quiet
            # logger.debug(result.stdout)
            
        except subprocess.CalledProcessError as e:
            status = "failed"
            err_msg = f"Command failed with exit code {e.returncode}. Stderr: {e.stderr}"
            logger.error(f"[{task_name}] Failed: {err_msg}")
        except Exception as e:
            status = "failed"
            err_msg = str(e)
            logger.error(f"[{task_name}] Exception: {e}", exc_info=True)
            
        end_t = get_turkey_now()
        dur = time.time() - start_ts
        
        logger.info(f"[{task_name}] Finished in {dur:.2f}s | Status: {status}")
        
        return MaintenanceTaskResult(
            name=task_name,
            status=status,
            started_at=start_t,
            finished_at=end_t,
            duration_sec=dur,
            error=err_msg
        )

    def run(self) -> MaintenanceRunSummary:
        start_run = get_turkey_now()
        logger.info(f"🚀 Starting Offline Maintenance ID={self.run_id} Mode={self.mode}")
        
        # 1. Define Tasks based on mode
        # We leverage existing CLI scripts via python -m ...
        # Ensure PYTHONPATH is set correctly in environment or invoke via python src/...
        
        python_exe = sys.executable
        
        # Task Definitions
        scripts = []
        
        # Common args helper
        def get_args(symbol_arg: str, all_arg: str) -> List[str]:
            if self.mode == "symbol" and len(self.symbols) == 1:
                return [symbol_arg, self.symbols[0]]
            else:
                return [all_arg]

        # --- A. RALLY SCANS ---
        
        # Fast15
        if self.mode in ["full", "fast", "symbol"]:
            # src/tezaver/rally/run_fast15_rally_scan.py
            cmd_args = get_args("--symbol", "--all-symbols")
            scripts.append({
                "name": "Fast15 Scan",
                "cmd": [python_exe, "src/tezaver/rally/run_fast15_rally_scan.py"] + cmd_args
            })
            
        # Time-Labs 1h
        if self.mode in ["full", "fast", "symbol"]:
            # src/tezaver/rally/run_time_labs_scan.py --tf 1h
            cmd_args = get_args("--symbol", "--all-symbols")
            scripts.append({
                "name": "Time-Labs 1h",
                "cmd": [python_exe, "src/tezaver/rally/run_time_labs_scan.py", "--tf", "1h"] + cmd_args
            })

        # Time-Labs 4h
        if self.mode in ["full", "fast", "symbol"]:
             cmd_args = get_args("--symbol", "--all-symbols")
             scripts.append({
                "name": "Time-Labs 4h",
                "cmd": [python_exe, "src/tezaver/rally/run_time_labs_scan.py", "--tf", "4h"] + cmd_args
            })

        # --- B. SIM LAYERS ---
        
        # Affinity Export (Sim Scoreboard runs implicitly inside? No, affinity export runs scoreboard logic usually)
        # Actually run_sim_affinity_export.py calculates stats from existing sim results or triggers new sim?
        # Looking at previous implementation of `run_sim_affinity_export`: it computes affinity based on cached scoreboard or runs it.
        # Ideally we want fresh simulation.
        # run_sim_affinity_export.py calls `run_sim_affinity_export_for_symbol` -> `sim_scoreboard.generate_affinity_for_symbol`
        # `generate_affinity_for_symbol` calls `run_preset_scoreboard` which DOES RUN SIMULATION.
        # So yes, this triggers fresh simulation.
        
        if self.mode == "full" or self.mode == "symbol":
             cmd_args = get_args("--symbol", "--all-symbols")
             scripts.append({
                "name": "Sim Affinity",
                "cmd": [python_exe, "src/tezaver/sim/run_sim_affinity_export.py"] + cmd_args
            })
            
             # Promotion Export (Fast/cheap but needs Affinity data)
             scripts.append({
                "name": "Sim Promotion",
                "cmd": [python_exe, "src/tezaver/sim/run_sim_promotion_export.py"] + cmd_args
            })
            
        # --- C. RALLY RADAR ---
        
        if self.mode in ["full", "fast", "symbol"]:
             cmd_args = get_args("--symbol", "--all-symbols")
             scripts.append({
                "name": "Rally Radar",
                "cmd": [python_exe, "src/tezaver/rally/run_rally_radar_export.py"] + cmd_args
            })
            
        # 2. Execute Tasks
        for s in scripts:
            res = self._run_subprocess(s["cmd"], s["name"])
            self.tasks.append(res)
            
        # 3. Summary
        finished_run = get_turkey_now()
        
        # Calculate overall status
        statuses = [t.status for t in self.tasks]
        if all(s == "success" for s in statuses):
            final_status = "success"
        elif all(s == "failed" for s in statuses):
            final_status = "failed"
        else:
            final_status = "partial"
            
        summary = MaintenanceRunSummary(
            run_id=self.run_id,
            mode=self.mode,
            started_at=start_run,
            finished_at=finished_run,
            overall_status=final_status,
            tasks=self.tasks
        )
        
        # 4. Record State
        try:
            record_offline_maintenance_run(summary)
        except Exception as e:
            logger.error(f"Failed to record maintenance run state: {e}")
            
        logger.info(f"✅ Offline Maintenance Completed | Status: {final_status}")
        return summary
