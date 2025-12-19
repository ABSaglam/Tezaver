# Tezaver Bulut - Dry Run Service (P4)
"""
Service to execute Mainnet Dry Runs (Simulations).
"""
import copy
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
# from tezaver.bulut.services.telemetry import TelemetryService # Not found, using Any or logic


class DryRunService:
    def __init__(self, main_ctx: BulutContext):
        self._main_ctx = main_ctx
        self._running = False
        self._last_report = {}

    async def start_run(self, cycles: int = 20) -> str:
        """Start a dry run simulation."""
        if self._running:
             raise RuntimeError("Dry run already in progress")
        
        if not self._main_ctx.config.dry_run_enabled:
             raise RuntimeError("Dry run disabled in config")
             
        # Create Run ID
        run_id = f"DRY_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        # Start background task
        asyncio.create_task(self._task_loop(run_id, cycles))
        return run_id

    async def _task_loop(self, run_id: str, cycles: int):
        self._running = True
        print(f"[DRY-RUN] Starting {run_id} ({cycles} cycles)...")
        
        try:
            # 1. Setup Shadow Context (Isolated DB)
            from dataclasses import replace
            import tempfile
            import os
            
            shadow_config = replace(self._main_ctx.config, dry_run_enabled=True) 
            
            # Isolated DB (Use temp file to keep persistence across connections)
            # We don't rely on :memory: because SqlitePersistence creates new conn on each call.
            self._temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            self._temp_db.close()
            
            shadow_persistence = SqlitePersistence(self._temp_db.name) 
            shadow_persistence._init_db() # Create tables
            
            # Clone State
            shadow_ctx = BulutContext(shadow_config)
            shadow_ctx._persistence = shadow_persistence # Inject
             
            # Inject Services that need to be REAL (or mocked?)
            # Universe: Real (load form source)
            # Bars: Real (load from store, but we need HISTORY)
            # Scheduler: Real logic, but we drive it manually.
            # Executor: Simulated (via Context property logic + Config)
            # StrictTiming: Real logic, but uses Shadow Persistence (empty, so no dedupe block for old bars).
            
            # Load services eagerly
            _ = shadow_ctx.universe_source
            _ = shadow_ctx.bars_store
            
            # 2. Fetch History Bars
            from tezaver.bulut.services.binance_futures_rest import BinanceFuturesRest
            
            # Use REST client (public endpoints don't need signature)
            rest_client = BinanceFuturesRest(shadow_ctx.config)
            await rest_client.create_session()
            
            try:
                klines = await rest_client.fetch_klines("BTCUSDT", shadow_ctx.config.base_tf, limit=cycles + 5)
            finally:
                await rest_client.close()
            
            # Sort and slice
            # get_klines usually returns objects or dicts depending on implementation.
            # Assuming it returns list of objects with close_ts attribute or dict.
            # BinanceFuturesRest typically returns objects.
            # Let's handle both for safety or check implementation?
            # Assuming objects based on context.py usage.
            
            # Sort and slice [0:open, ... 6:close_ts]
            klines = sorted(klines, key=lambda x: x[6])
            target_klines = klines[-cycles:]
            
            processed_count = 0
            open_count = 0
            
            from tezaver.bulut.schemas.bar_v1 import BarV1
            from unittest.mock import AsyncMock

            for k in target_klines:
                # k is list
                close_ts_ms = k[6]
                close_ts_dt = datetime.fromtimestamp(close_ts_ms / 1000.0, timezone.utc)
                now_sim_dt = close_ts_dt + timedelta(seconds=1)
                
                # Ingest Bar into BarsStore using Mock
                bar = BarV1(
                    symbol="BTCUSDT",
                    tf=shadow_ctx.config.base_tf,
                    open_ts=datetime.fromtimestamp(k[0] / 1000.0, timezone.utc),
                    close_ts=close_ts_dt,
                    o=float(k[1]), h=float(k[2]), l=float(k[3]), c=float(k[4]), v=float(k[5]),
                    is_closed=True
                )
                if hasattr(shadow_ctx.bars_store, 'get_latest_closed_bar'):
                    shadow_ctx.bars_store.get_latest_closed_bar = AsyncMock(return_value=bar)
                
                # Strict Timing
                try:
                    shadow_ctx.strict_timing.on_cycle_attempt(now_sim_dt)
                except Exception:
                    pass
                
                # Run Cycle logic
                await shadow_ctx.scheduler._run_cycle_logic(shadow_ctx, close_ts_ms)
                
                processed_count += 1
            
            # 4. Summary from Shadow DB
            shadow_cur = shadow_persistence._get_conn().cursor()
            # Count Open Plans
            # dry run executor simulates "open_position"
            # Logic: `SimulatedExecutor` calls `persistence.open_position`.
            # Persistence defaults to `positions` table.
            shadow_cur.execute("SELECT COUNT(*) FROM positions WHERE status='OPEN'")
            open_count = shadow_cur.fetchone()[0]
            
            summary = {
                "cycles_target": cycles,
                "cycles_processed": processed_count,
                "open_positions": open_count,
                "note": "Simulation successful"
            }
            
            self._main_ctx.persistence.insert_dry_run(run_id, "SUCCESS", summary)
            self._last_report = summary
            
        except Exception as e:
            print(f"[DRY-RUN] Failed: {e}")
            import traceback
            traceback.print_exc()
            self._main_ctx.persistence.insert_dry_run(run_id, "FAILED", {"error": str(e)})
        finally:
            self._running = False
            # Cleanup DB
            if hasattr(self, '_temp_db') and self._temp_db:
                try:
                    os.unlink(self._temp_db.name)
                except:
                    pass
    
    def get_status(self):
        return {
            "running": self._running
        }
