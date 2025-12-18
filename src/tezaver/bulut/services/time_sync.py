# Tezaver Bulut - Time Sync Service
"""
Service to synchronize local time with Binance server time.
Calculates offset and provides corrected timestamp.
"""

import time
import asyncio
import aiohttp
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class TimeSyncService:
    def __init__(self, config: BulutConfig, telemetry: NdjsonTelemetry):
        self._config = config
        self._telemetry = telemetry
        
        self._offset_ms: int = 0
        self._last_sync_ts: float = 0
        self._last_server_time: int = 0
        self._last_error: Optional[str] = None
        self._syncing: bool = False
        
        # Base URL for public time endpoint (fapi)
        self._base_url = "https://fapi.binance.com"
        if config.use_testnet:
            self._base_url = "https://testnet.binancefuture.com"

    async def refresh(self):
        """
        Fetch server time and calculate offset.
        offset = server_time - local_time
        """
        if not self._config.time_sync_enabled:
            return

        if self._syncing:
            return
            
        self._syncing = True
        try:
            url = f"{self._base_url}/fapi/v1/time"
            # We use a raw session here to avoid circular dependency with signed client
            # or overhead of governor for this simple check?
            # Ideally governor should be used, but TimeSync is critical infrastructure.
            # I'll use aiohttp directly for now.
            
            t0 = time.time() * 1000
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        server_time = data["serverTime"]
                        t1 = time.time() * 1000
                        
                        # Latency adjustment: assume server time was captured at (t0 + t1)/2
                        # rigorous: offset = server_time - (t0 + t1)/2
                        # But standard simple sync: calculate round trip
                        rtt = t1 - t0
                        local_time_est = t1 - (rtt / 2) 
                        
                        # server_time is "true" time.
                        # offset = server - local
                        new_offset = int(server_time - local_time_est)
                        
                        self._offset_ms = new_offset
                        self._last_sync_ts = time.time()
                        self._last_server_time = server_time
                        self._last_error = None
                        
                        # Telemetry
                        self._telemetry.emit_custom("TIME_SYNC_OK", {
                            "offset_ms": new_offset,
                            "rtt_ms": int(rtt),
                            "server_time": server_time
                        })
                        
                        # Check skew immediatley
                        if abs(new_offset) > self._config.time_sync_max_skew_ms:
                             self._telemetry.emit_custom("TIME_SYNC_SKEW_HIGH", {
                                "offset_ms": new_offset,
                                "limit": self._config.time_sync_max_skew_ms
                            })
                    else:
                        err = f"HTTP {resp.status}"
                        self._last_error = err
                        self._telemetry.emit_custom("TIME_SYNC_FAIL", {"error": err})
                        
        except Exception as e:
            self._last_error = str(e)
            self._telemetry.emit_custom("TIME_SYNC_FAIL", {"error": str(e)})
        finally:
            self._syncing = False

    def now_ms(self) -> int:
        """Get corrected current timestamp in ms."""
        local_ms = int(time.time() * 1000)
        if not self._config.time_sync_enabled:
            return local_ms
        return local_ms + self._offset_ms

    def is_healthy(self) -> Tuple[bool, Dict[str, Any]]:
        """Check if sync is healthy (skew acceptable, no error)."""
        if not self._config.time_sync_enabled:
            return True, {"enabled": False}
        
        details = {
            "offset_ms": self._offset_ms,
            "last_error": self._last_error,
            "ts_ago": int(time.time() - self._last_sync_ts) if self._last_sync_ts else -1
        }
        
        if self._last_error:
            return False, {**details, "reason": "LAST_SYNC_FAILED"}
            
        if abs(self._offset_ms) > self._config.time_sync_max_skew_ms:
            return False, {**details, "reason": "SKEW_TOO_HIGH"}
            
        # Optional: check staleness? 
        # If last sync was > 2 * refresh_interval?
        # User didn't specify stale check, but implied via reload_if_due.
        
        return True, details

    async def reload_if_due(self):
        """Trigger refresh if time elapsed."""
        if not self._config.time_sync_enabled:
            return
            
        now = time.time()
        if (now - self._last_sync_ts) >= self._config.time_sync_refresh_seconds:
            await self.refresh()
