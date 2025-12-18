# Tezaver Bulut - User Data Stream
"""
Manages Binance Futures User Data Stream (WebSocket).
Handles ListenKey creation, keepalive, and event parsing.
"""

import asyncio
import json
import time
import aiohttp
from typing import Optional, Any, Callable
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class UserDataStream:
    def __init__(
        self, 
        config: BulutConfig, 
        client: BinanceFuturesSigned, 
        telemetry: NdjsonTelemetry,
        # We need injection of services to update them
        # Circular imports risk if we import services here directly?
        # We pass "context" or callbacks?
        # Ideally, we emit internal events or call methods on dependencies.
        # Let's accept dependencies or context wrapper.
        # Better: Accept `persistence` and callbacks or context.
        # For implementation speed, let's accept `context` (passed in start or via property?)
        # Or injection in init.
        # We need access to: 
        # 1. FillSyncService (for ORDER_TRADE_UPDATE -> sync_fill usually done via REST, but now event driven?)
        # 2. Persistence (update trades)
        # 3. Context State (Positions)
        # Let's pass the context in "start" or init.
        # Init is cleaner if possible, but context creates this service.
        # So Context can assume "this service has a reference to Context"?
        # Or we pass `reconcile_callback`, `fill_callback`.
        # Let's use `on_order_update` and `on_account_update` callbacks set by Context?
        # Or simpler: pass `ctx` to `start()` and store it.
    ):
        self._config = config
        self._client = client
        self._telemetry = telemetry
        self._ctx: Any = None # Set in start()
        self._reducer: Any = None # Set via set_reducer or ctx
        
        self._listen_key: Optional[str] = None
        self._running = False
        self._ws_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        
        self.last_event_ts: float = 0.0
        self.connected = False
        self.listen_key_created_at: float = 0.0

    def set_reducer(self, reducer: Any):
        """Inject State Reducer (v0.22)."""
        self._reducer = reducer

    async def start(self, ctx: Any):
        """Start User Data Stream (legacy/managed)."""
        # If called directly, run in background
        if not self._config.user_data_ws_enabled:
            return
        self._running = True
        self._ctx = ctx
        self._ws_task = asyncio.create_task(self.run_forever(ctx))

    async def run_forever(self, ctx: Any):
        """Run stream loop forever (Supervisor mode)."""
        if not self._config.user_data_ws_enabled:
             return
             
        self._ctx = ctx
        self._running = True
        if not self._reducer and hasattr(ctx, "state_reducer"):
            self._reducer = ctx.state_reducer
            
        print("[UserDataStream] Starting (Supervisor Mode)...")
        
        # We need to run Keepalive AND WS Loop concurrently.
        # If one crashes, supervisor restarts both?
        # Yes, wrapper calls run_forever().
        # So we should use asyncio.gather or task group here?
        # If WS loop crashes, we want to restart.
        # If Keepalive crashes?
        # Let's run them in gather.
        
        try:
             # Create ListenKey first
             try:
                self._listen_key = await self._client.create_listen_key()
                self.listen_key_created_at = time.time()
             except Exception as e:
                 # If creation fails, should we raise to supervisor?
                 # Yes, supervisor will backoff and retry.
                 raise e
                 
             await asyncio.gather(
                 self._ws_loop(),
                 self._keepalive_loop()
             )
        except Exception as e:
             # Propagate to supervisor
             raise e
        finally:
             self._running = False

    async def stop(self):
        """Stop the stream."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        
        if self._keepalive_task:
            self._keepalive_task.cancel()
            
        if self._listen_key:
            try:
                await self._client.close_listen_key()
            except:
                pass
            self._listen_key = None
            
        self.connected = False
        print("[UserDataStream] Stopped.")

    async def _keepalive_loop(self):
        """Send keepalive every 10 minutes (config safe buffer)."""
        interval = self._config.user_data_keepalive_seconds 
        while self._running:
            await asyncio.sleep(interval)
            try:
                await self._client.keepalive_listen_key()
                # Beat
                if self._ctx and hasattr(self._ctx, "task_supervisor"):
                     self._ctx.task_supervisor.beat("user_data", "Keepalive OK")
            except Exception as e:
                print(f"[UserDataStream] Keepalive error: {e}")

    async def _ws_loop(self):
        """Main WebSocket connection loop with reconnection."""
        backoff = self._config.user_data_reconnect_backoff_ms / 1000.0
        
        while self._running:
            
            # ... ListenKey logic moved to start/run_forever mainly, 
            # but if we lost it and loop continues?
            # If run_forever crashed, we restart fresh with new key.
            # So _ws_loop doesn't need to recreate logic as much if supervisor handles restart?
            # Actually supervisor restarts the whole run_forever().
            # So if WS disconnects cleanly (network glitch) we might want to stay in loop.
            # If exception, we exit loop and Supervisor restarts.
            
            if not self._listen_key:
                 # Re-acquire if missing inside loop (e.g. if we clear it on error)
                 # Or treat as critical error and raise to Supervisor?
                 # Let's raise to Supervisor.
                 raise RuntimeError("ListenKey missing in WS Loop")

            url = f"{self._config.user_data_ws_base_url}/{self._listen_key}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url) as ws:
                        self.connected = True
                        self._telemetry.emit("USER_DATA_CONNECTED", {"url": "..."}) 
                        # Beat
                        if self._ctx and hasattr(self._ctx, "task_supervisor"):
                             self._ctx.task_supervisor.beat("user_data", "Connected")
                        
                        backoff = self._config.user_data_reconnect_backoff_ms / 1000.0
                        
                        async for msg in ws:
                            if not self._running:
                                break
                            
                            # Beat on activity
                            # Don't beat on every message? Only throttle?
                            # Supervisor cares about ~N seconds.
                            # Let's just beat on connect/maintain.
                                
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                    await self._handle_message(data)
                                except Exception as e:
                                    print(f"[UserDataStream] Parse error: {e}")
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                raise RuntimeError(f"WS Error: {ws.exception()}")
                                
                    self.connected = False
                    self._telemetry.emit("USER_DATA_DISCONNECTED")
                    
            except Exception as e:
                # Raise to supervisor to trigger backoff restart found in supervisor?
                # Or handle local backoff?
                # Supervisor has better alerting.
                # Let's raise.
                raise e
            
            # If we break cleanly (server close?), we loop or raise?
            if self._running:
                 raise RuntimeError("WS Connection Closed Unexpectedly")


    async def _handle_message(self, data: dict):
        """Process incoming WS message."""
        evt_type = data.get("e")
        event_time = data.get("E", 0) # Event time
        self.last_event_ts = time.time()
        
        # ORDER_TRADE_UPDATE
        if evt_type == "ORDER_TRADE_UPDATE":
            o = data.get("o", {})
            # v0.22 Reducer
            if self._reducer:
                self._reducer.apply_order_update(o, source="USER_DATA")
            
        # ACCOUNT_UPDATE
        elif evt_type == "ACCOUNT_UPDATE":
            a = data.get("a", {})
            # Inject Event Time for Reducer OOO check
            if isinstance(a, dict):
                a["_E"] = event_time
            
            # v0.22 Reducer
            if self._reducer:
                self._reducer.apply_account_update(a, source="USER_DATA")
    
    # Deprecated v0.21 methods (_process_order_update, _process_account_update) removed in v0.22 update.
