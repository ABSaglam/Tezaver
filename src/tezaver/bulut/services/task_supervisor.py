# Tezaver Bulut - Task Supervisor
"""
Task Supervisor for managing long-running background tasks.
Handles auto-restarts, heartbeats, and crash alerts.
"""

import asyncio
import time
import traceback
from typing import Dict, Callable, Awaitable, Any, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

CoroFactory = Callable[[], Awaitable[Any]]

class TaskSupervisor:
    def __init__(
        self,
        config: BulutConfig,
        persistence: SqlitePersistence,
        telemetry: NdjsonTelemetry
    ):
        self._config = config
        self._persistence = persistence
        self._telemetry = telemetry
        
        self._tasks: Dict[str, CoroFactory] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._stopped_flags: Dict[str, bool] = {}
        
        self._supervisor_running = False

    def register(self, name: str, factory: CoroFactory):
        """Register a task factory."""
        self._tasks[name] = factory

    async def start_all(self):
        """Start all registered tasks."""
        self._supervisor_running = True
        print("[Supervisor] Starting all tasks...")
        
        for name, factory in self._tasks.items():
            self._start_task(name, factory)

    def _start_task(self, name: str, factory: CoroFactory):
        """Spawn a managed task."""
        if name in self._running_tasks and not self._running_tasks[name].done():
            return
            
        self._stopped_flags[name] = False
        # Create wrapper task
        self._running_tasks[name] = asyncio.create_task(
            self._task_wrapper(name, factory),
            name=f"sup-{name}"
        )

    async def stop_all(self):
        """Stop all tasks."""
        print("[Supervisor] Stopping all tasks...")
        self._supervisor_running = False
        
        for name in list(self._running_tasks.keys()):
            self._stopped_flags[name] = True
            task = self._running_tasks[name]
            task.cancel()
        
        # Wait for all?
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
            self._running_tasks.clear()

    async def _task_wrapper(self, name: str, factory: CoroFactory):
        """
        Wraps task execution with restart logic.
        """
        backoff = 0.5 # start 500ms
        max_backoff = 8.0 # max 8s
        
        print(f"[Supervisor] Task '{name}' started.")
        self._persistence.beat(name, status="OK", detail="Started")
        
        while self._supervisor_running and not self._stopped_flags.get(name, False):
            try:
                # Run the actual task
                await factory()
                
                # If it returns cleanly, it means it finished (maybe intended?)
                # If intended stop, we break loop. 
                # Assuming tasks are "infinite loops". If they return, they are done.
                print(f"[Supervisor] Task '{name}' finished normally.")
                self._persistence.beat(name, status="STOPPED", detail="Finished normally")
                break
                
            except asyncio.CancelledError:
                print(f"[Supervisor] Task '{name}' cancelled.")
                self._persistence.beat(name, status="STOPPED", detail="Cancelled")
                break
                
            except Exception as e:
                # Crash!
                err_msg = f"{type(e).__name__}: {str(e)}"
                stack = traceback.format_exc()
                print(f"[Supervisor] Task '{name}' CRASHED: {err_msg}")
                # print(stack) # detailed log if needed
                
                self._persistence.beat(name, status="CRASHED", detail=err_msg)
                
                self._telemetry.emit("TASK_RESTART", {
                    "task": name, "error": err_msg, "backoff": backoff
                })
                # Alert
                self._persistence.insert_alert(
                    level="ERROR", 
                    code="TASK_CRASH", 
                    message=f"Task '{name}' crashed (restarting in {backoff}s)",
                    details={"error": err_msg, "trace": stack}
                )
                
                # Backoff wait
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    break
                    
                backoff = min(backoff * 2.0, max_backoff)
                print(f"[Supervisor] Restarting '{name}' (attempt backoff {backoff}s)...")
                # Loop continues -> restarts factory()

    def beat(self, name: str, detail: str = ""):
        """Call this from within tasks to report health."""
        # Just proxy to persistence, maybe update local cache if needed?
        self._persistence.beat(name, status="OK", detail=detail)
