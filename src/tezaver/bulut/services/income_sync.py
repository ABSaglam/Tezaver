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

class IncomeSyncService:
    def __init__(self, config: BulutConfig, client: BinanceFuturesSigned, persistence: SqlitePersistence, telemetry, time_sync: TimeSyncService):
        self._config = config
        self._client = client
        self._persistence = persistence
        self._telemetry = telemetry
        self._time_sync = time_sync
        
        self._last_check_ms = 0
        self._refresh_interval_ms = getattr(config, "income_sync_refresh_seconds", 900) * 1000
        
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
        Returns stats dict.
        """
        now_ms = self._time_sync.now_ms()
        
        # Get cursor
        last_sync_ms = self._persistence.get_income_last_sync_ms()
        
        # Determine start time
        start_ms = last_sync_ms
        if start_ms == 0:
            # First run, lookback
            lookback_h = getattr(self._config, "income_sync_lookback_hours", 48)
            start_ms = now_ms - (lookback_h * 3600 * 1000)
            
        # Limit window to avoid huge requests if lookback is far?
        # Binance income limit is 1000. 
        # Actually userTrades limit 1000 is usually enough for 48h unless high frequency funding?
        # Funding is every 8h -> 6 entries per symbol per 48h.
        # If we query ALL symbols (symbol=None), we might hit limit quickly if we hold many positions.
        # Binance defaults: symbol=None gets income for "current account".
        # But wait, docs say "If symbol is not sent, it tracks all symbols".
        # So we should be careful about limit.
        
        limit = getattr(self._config, "income_sync_limit", 1000)
        types_str = getattr(self._config, "income_sync_types", "FUNDING_FEE")
        types = [t.strip() for t in types_str.split(",") if t.strip()]
        
        total_inserted = 0
        total_count = 0
        
        # We might need pagination if range is large, but for now simple sync
        # We update cursor to now_ms afterwards.
        # Ideally we update cursor to the timestamp of the last event fetched + 1.
        # But if we fetch multiple types, timestamps might verify.
        # Safer: Use max(timestamp_received) as new cursor.
        
        max_ts_seen = start_ms
        
        for i_type in types:
            try:
                # We fetch from start_ms to now_ms
                # Note: Binance might return max 1000 items. 
                # If we hit 1000, we might strictly need pagination.
                # Here simplified implementation assuming 15m sync interval keeps it small.
                
                events = await self._client.get_income_history(
                    income_type=i_type,
                    start_time=start_ms,
                    end_time=now_ms,
                    limit=limit
                )
                
                if events and not (isinstance(events, dict) and events.get("error")):
                    count = len(events)
                    total_count += count
                    
                    inserted = self._persistence.upsert_income_events(events)
                    total_inserted += inserted
                    
                    # Update max_ts
                    for e in events:
                        ts = int(e.get("time", 0))
                        if ts > max_ts_seen:
                            max_ts_seen = ts
                    
                    self._telemetry.emit("INCOME_SYNC_OK", {
                        "type": i_type,
                        "count": count,
                        "inserted": inserted,
                        "start_ms": start_ms,
                        "end_ms": now_ms
                    })
                elif not events:
                    pass # Empty
                else:
                    self._telemetry.emit("INCOME_SYNC_FAIL", {
                        "type": i_type,
                        "error": str(events)
                    })
                    
            except Exception as e:
                self._telemetry.emit("INCOME_SYNC_FAIL", {
                    "type": i_type,
                    "error": str(e)
                })
        
        # Create non-USDT alerts
        if total_count > 0 and getattr(self._config, "alert_on_non_usdt_fee", True):
             res = self._persistence.get_today_income_sum_utc(types=types)
             non_usdt = res.get("non_usdt_count", 0)
             if non_usdt > 0:
                 self._telemetry.emit("ALERT", {
                     "level": "WARN",
                     "code": "NON_USDT_INCOME_UNACCOUNTED",
                     "message": f"Found {non_usdt} non-USDT income events today. Total PnL might be inaccurate.",
                     "details": {"count": non_usdt}
                 })
                 self._persistence.insert_alert(
                     "WARN", 
                     "NON_USDT_INCOME_UNACCOUNTED", 
                     f"Found {non_usdt} non-USDT income events today.",
                     {"count": non_usdt}
                 )

        # Update cursor (only if we actually moved forward)
        # We add 1ms to avoid fetching same event next time
        if max_ts_seen > start_ms:
             self._persistence.set_income_last_sync_ms(max_ts_seen + 1)
             
        return {
            "last_sync_ms": max_ts_seen if max_ts_seen > start_ms else last_sync_ms,
            "inserted": total_inserted,
            "checked_types": types
        }
