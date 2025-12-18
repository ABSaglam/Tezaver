# Tezaver Bulut - Rate Limit Governor
"""
Centralized rate limit governor for Binance Futures API.
Implements Sliding Window / Fixed Window hybrid for weight tracking.
"""

import time
import asyncio
import random
from typing import Optional
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class RateLimitGovernor:
    def __init__(self, config: BulutConfig, telemetry: Optional[NdjsonTelemetry] = None):
        self._config = config
        self._telemetry = telemetry
        
        self._window_start = time.time()
        self._used_market = 0
        self._used_trade = 0
        self._lock = asyncio.Lock()
        
    def _reset_window_if_needed(self):
        now = time.time()
        if now - self._window_start >= 60.0:
            # Emit telemetry for closing window
            if self._telemetry:
                 # Market Stats
                 self._telemetry.emit_request_budget(
                     used=self._used_market,
                     budget=self._config.rate_limit_budget_market_per_min,
                     window_age=now - self._window_start,
                     channel="MARKET"
                 )
                 # Trade Stats
                 self._telemetry.emit_request_budget(
                     used=self._used_trade,
                     budget=self._config.rate_limit_budget_trade_per_min,
                     window_age=now - self._window_start,
                     channel="TRADE"
                 )
            
            # Reset
            self._window_start = now
            self._used_market = 0
            self._used_trade = 0

    async def acquire(self, channel: str, endpoint_key: str):
        """
        Acquire rate limit budget for channel ("MARKET" or "TRADE").
        Endpoint key format: "METHOD:/path" (e.g. "GET:/fapi/v1/klines")
        """
        if not self._config.rate_limit_enabled:
            return

        # Determine weight
        weight = self._config.endpoint_weights.get(endpoint_key)
        if weight is None:
            weight = 10 # Penalty for unknown
            print(f"[GOVERNOR] Warning: Unknown endpoint {endpoint_key}, using weight 10.")
            # TODO: Emit WARN_UNKNOWN_WEIGHT telemetry
            
        async with self._lock:
            self._reset_window_if_needed()
            
            # Select Budget & Counter
            if channel == "MARKET":
                limit = self._config.rate_limit_budget_market_per_min
                used = self._used_market
            elif channel == "TRADE":
                limit = self._config.rate_limit_budget_trade_per_min
                used = self._used_trade
            else:
                # Fallback to trade strictness?
                limit = 200
                used = self._used_trade
            
            safety = int(limit * self._config.rate_limit_safety_pct)
            
            # Check if we have budget
            if used + weight > safety:
                # Calculate sleep time
                now = time.time()
                reset_time = self._window_start + 60.0
                sleep_sec = max(0.1, reset_time - now)
                
                # Emit throttle
                if self._telemetry:
                    self._telemetry.emit_rate_limit_throttle(int(sleep_sec * 1000), endpoint_key)
                
                print(f"[GOVERNOR] Throttling {channel} for {sleep_sec:.2f}s (Used: {used}, Weight: {weight})")
                await asyncio.sleep(sleep_sec)
                
                # Force reset
                self._window_start = time.time()
                self._used_market = 0
                self._used_trade = 0
                
                # Re-select used (it is 0 now)
                used = 0
                
            # Increment
            if channel == "MARKET":
                self._used_market += weight
            else:
                self._used_trade += weight
            
    # record_usage, handle_backoff, get_status update...
            
    def record_usage(self, weight: int):
        """Record usage from headers if available (optional sync update)."""
        # Ideally we parse check 'X-MBX-USED-WEIGHT-1M' header
        # But simply tracking 'acquire' calls is safer proactively.
        # If we trust headers, we can implement sync logic here.
        pass

    async def handle_backoff(self, attempt: int, error: str):
        """
        Handle backoff sleep for 429/418 errors.
        """
        # Exponential backoff with jitter
        # Base * 2^attempt
        factor = 2 ** attempt
        base = self._config.backoff_base_ms
        cap = self._config.backoff_max_ms
        
        sleep_ms = min(cap, base * factor)
        # Jitter +- 20%
        jitter = random.uniform(0.8, 1.2)
        sleep_ms = int(sleep_ms * jitter)
        
        if self._telemetry:
            self._telemetry.emit_backoff_applied(attempt, sleep_ms, error)
            
        await asyncio.sleep(sleep_ms / 1000.0)

    def get_status(self):
        return {
            "window_start": self._window_start,
            "market": {
                "used": self._used_market,
                "budget": self._config.rate_limit_budget_market_per_min
            },
            "trade": {
                "used": self._used_trade,
                "budget": self._config.rate_limit_budget_trade_per_min
            }
        }
