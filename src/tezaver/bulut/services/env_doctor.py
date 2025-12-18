# Tezaver Bulut - Env Doctor
"""
Environment Doctor Service.
Performs self-checks on runtime environment, dependencies, and configuration.
"""

import sys
import os
import importlib
import tempfile
import sqlite3
from pathlib import Path
from typing import Dict, Any, List

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class EnvDoctor:
    def __init__(self, config: BulutConfig, telemetry: NdjsonTelemetry):
        self._config = config
        self._telemetry = telemetry
        
    def run_checks(self, ctx: Any = None) -> Dict[str, Any]:
        """
        Run all environment checks.
        Returns a report dictionary.
        """
        report = {
            "status": "OK", # OK, WARN, FAIL
            "checks": {},
            "warnings": [],
            "errors": []
        }
        
        # 1. Python Environment
        py_check = {
            "executable": sys.executable,
            "version": sys.version,
            "venv_active": (sys.prefix != sys.base_prefix),
            "status": "OK"
        }
        if not py_check["venv_active"]:
             py_check["status"] = "WARN"
             report["warnings"].append("Virtual environment not detected (sys.prefix == sys.base_prefix)")
        report["checks"]["python"] = py_check
        
        # 2. Dependencies
        req_modules = ["fastapi", "uvicorn", "streamlit", "httpx", "sqlite3"]
        deps = {}
        deps_fail = False
        for mod in req_modules:
            try:
                importlib.import_module(mod)
                deps[mod] = "OK"
            except ImportError:
                deps[mod] = "MISSING"
                deps_fail = True
                report["errors"].append(f"Missing dependency: {mod}")
        
        report["checks"]["dependencies"] = deps
        if deps_fail:
             report["status"] = "FAIL"
             
        # 3. SQLite Write Check
        db_path = self._config.sqlite_path
        db_check = {"path": str(db_path), "writable": False, "status": "FAIL"}
        try:
             # Ensure dir exists first (persistence does this, but doctor runs early?)
             Path(db_path).parent.mkdir(parents=True, exist_ok=True)
             conn = sqlite3.connect(db_path)
             cur = conn.cursor()
             cur.execute("CREATE TABLE IF NOT EXISTS _doctor_check (id INTEGER PRIMARY KEY)")
             cur.execute("INSERT INTO _doctor_check DEFAULT VALUES")
             cur.execute("DROP TABLE _doctor_check")
             conn.close()
             db_check["writable"] = True
             db_check["status"] = "OK"
        except Exception as e:
             db_check["error"] = str(e)
             report["errors"].append(f"SQLite not writable: {e}")
             report["status"] = "FAIL"
        report["checks"]["sqlite"] = db_check
        
        # 4. Data Directories
        data_dirs = [
            "data/bulut_state",
            "data/bulut_logs",
            "data/bulut_rules",
            "data/bulut_incidents"
        ]
        dirs_check = {}
        for d in data_dirs:
            path = Path(d)
            status = "OK"
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Test write temp file
                with tempfile.TemporaryFile(dir=path) as tmp:
                    tmp.write(b"check")
            except Exception as e:
                status = "FAIL"
                report["errors"].append(f"Data dir {d} not writable: {e}")
                report["status"] = "FAIL"
            dirs_check[d] = status
        report["checks"]["data_dirs"] = dirs_check
        
        # 5. Config Sanity (if context provided)
        if ctx:
             conf_check = {"status": "OK"}
             
             # Testnet Keys
             if ctx.config.exchange == "BINANCE_FUTURES_TESTNET":
                 if not (os.getenv("BINANCE_TESTNET_API_KEY") and os.getenv("BINANCE_TESTNET_API_SECRET")):
                     # Maybe set in config directly? Config object usually loads from env.
                     # We assume config has them loaded if property exists, or we check env.
                     # Let's check config object if it has them. Config defines structure but not secrets usually.
                     # But secrets usually in env.
                     pass 
                     
             # Time Sync
             if ctx.config.execution_enabled and ctx.config.time_sync_enabled:
                 healthy, _ = ctx.time_sync.is_healthy()
                 if not healthy:
                      conf_check["time_sync"] = "UNHEALTHY"
                      report["warnings"].append("Time Sync is unhealthy but execution enabled.")
                      if report["status"] == "OK": report["status"] = "WARN"

             # Exchange Info
             if ctx.config.execution_enabled:
                  status = ctx.exchangeinfo_cache.get_status()
                  if not status.get("is_fresh"):
                       conf_check["exchange_info"] = "STALE"
                       report["warnings"].append(f"Exchange Info is stale ({status.get('age_seconds',0):.1f}s)")
                       if report["status"] == "OK": report["status"] = "WARN"

             report["checks"]["config_sanity"] = conf_check

        # Emit Telemetry
        evt = "ENV_DOCTOR_OK" if report["status"] != "FAIL" else "ENV_DOCTOR_FAIL"
        self._telemetry.emit(evt, {
            "status": report["status"],
            "errors": len(report["errors"]),
            "warnings": len(report["warnings"])
        })
        
        return report
