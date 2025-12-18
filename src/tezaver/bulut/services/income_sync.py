# Tezaver Bulut - Income Sync Service
"""
Syncs income events (Funding Fee, etc.) from Binance to local DB.
"""

import time
import asyncio
from typing import List, Optional
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.time_sync import TimeSyncService

from tezaver.bulut.services.fx_rate_cache import FxRateCache

class IncomeSyncService:
    def __init__(self, config: BulutConfig, client: BinanceFuturesSigned, persistence: SqlitePersistence, telemetry, time_sync: TimeSyncService, fx_cache: FxRateCache = None):
        self._config = config
        self._client = client
        self._persistence = persistence
        self._telemetry = telemetry
        self._time_sync = time_sync
        self._fx_cache = fx_cache
        
        self._last_check_ms = 0
        self._refresh_interval_ms = getattr(config, "income_sync_refresh_seconds", 900) * 1000
    
    # ... reload_if_due unchanged ...
    async def reload_if_due(self):
        """Check if sync is due and run it if necessary."""
        if not getattr(self._config, "income_sync_enabled", True):
            return

        now = self._time_sync.now_ms()
        if now - self._last_check_ms > self._refresh_interval_ms:
            await self.sync_now()
            self._last_check_ms = now

    async def sync_now(self, force: bool = False) -> dict:
        """
        Force sync income events.
        """
        now_ms = self._time_sync.now_ms()
        
        last_sync_ms = self._persistence.get_income_last_sync_ms()
        start_ms = last_sync_ms
        if start_ms == 0:
            lookback_h = getattr(self._config, "income_sync_lookback_hours", 48)
            start_ms = now_ms - (lookback_h * 3600 * 1000)
            
        limit = getattr(self._config, "income_sync_limit", 1000)
        types_str = getattr(self._config, "income_sync_types", "FUNDING_FEE")
        types = [t.strip() for t in types_str.split(",") if t.strip()]
        
        total_inserted = 0
        total_count = 0
        max_ts_seen = start_ms
        
        for i_type in types:
            try:
                events = await self._client.get_income_history(
                    income_type=i_type,
                    start_time=start_ms,
                    end_time=now_ms,
                    limit=limit
                )
                
                if events and not (isinstance(events, dict) and events.get("error")):
                    # Pre-process for FX conversion (v0.19)
                    for e in events:
                        asset = e.get("asset")
                        income = float(e.get("income", 0))
                        
                        # Set default None
                        e["income_usdt"] = None
                        e["fx_rate"] = None
                        e["fx_source"] = None
                        
                        if self._fx_cache:
                             # Try conversion
                             # Ideally we want the rate at the time of event? 
                             # But we only have current rate or rate in cache.
                             # For income history, using current rate is acceptable approximation if just synced?
                             # Or we should try to get cached rate. 
                             # FxRateCache.get_rate(asset) -> returns current cached or fetches fresh.
                             # But we are in a loop inside async function.
                             
                             rate = await self._fx_cache.get_rate(asset)
                             if rate:
                                 usdt, r, src = self._fx_cache.convert_to_usdt(asset, income, known_rate=rate)
                                 e["income_usdt"] = usdt
                                 e["fx_rate"] = r
                                 e["fx_source"] = src
                        
                        # Update persistence upsert to handle these new keys handled in persistence_sqlite.py?
                        # Wait, upsert_income_events in persistence_sqlite uses raw dict "e".
                        # But it constructs the INSERT data tuple manually from e.get().
                        # I need to update upsert_income_events in persistence_sqlite.py as well to use these keys!
                        # Ah, I updated table but NOT the upsert method in persistence_sqlite yet!
                        # I added only table alter. I must update upsert_income_events in persistence first/parallel.
                    
                    count = len(events)
                    total_count += count
                    
                    inserted = self._persistence.upsert_income_events(events)
                    total_inserted += inserted
                    
                    for e in events:
                        ts = int(e.get("time", 0))
                        if ts > max_ts_seen:
                            max_ts_seen = ts
                    
                    self._telemetry.emit("INCOME_SYNC_OK", {
                        "type": i_type,
                        "count": count,
                        "inserted": inserted
                    })
                # ... error handling ...
            except Exception as e:
                self._telemetry.emit("INCOME_SYNC_FAIL", {"type": i_type, "error": str(e)})

        # Create non-USDT alerts ONLY if conversion missing (v0.19)
        # get_today_income_sum_utc returns non_usdt_count = count of rows with asset!=USDT AND income_usdt IS NULL.
        if total_count > 0:
             res = self._persistence.get_today_income_sum_utc(types=types)
             unconverted = res.get("non_usdt_count", 0) # This is now defined as UNCONVERTED count in sql
             if unconverted > 0:
                 self._telemetry.emit("ALERT", {
                     "level": "WARN",
                     "code": "NON_USDT_INCOME_UNACCOUNTED",
                     "message": f"Found {unconverted} unconverted non-USDT income events today.",
                     "details": {"count": unconverted}
                 })
                 # Only insert alert if significant?
                 self._persistence.insert_alert(
                     "WARN", "NON_USDT_INCOME_UNACCOUNTED", f"Found {unconverted} unconverted non-USDT income events.", {"count": unconverted}
                 )

        if max_ts_seen > start_ms:
             self._persistence.set_income_last_sync_ms(max_ts_seen + 1)
             
        return {
            "last_sync_ms": max_ts_seen if max_ts_seen > start_ms else last_sync_ms,
            "inserted": total_inserted,
            "checked_types": types
        }
