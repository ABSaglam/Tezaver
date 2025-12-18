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
        self._used_weight = 0
        self._lock = asyncio.Lock()
        
    def _reset_window_if_needed(self):
        now = time.time()
        if now - self._window_start >= 60.0:
            # Emit telemetry for the closing window
            if self._telemetry:
                 self._telemetry.emit_request_budget(
                     used=self._used_weight,
                     budget=self._config.rate_limit_budget_per_min,
                     window_age=now - self._window_start
                 )
            
            # Reset
            self._window_start = now
            self._used_weight = 0

    async def acquire(self, weight: int, endpoint: str = "unknown"):
        """
        Acquire rate limit budget. handling sleeping if needed.
        """
        if not self._config.rate_limit_enabled:
            return

        async with self._lock:
            self._reset_window_if_needed()
            
            limit = self._config.rate_limit_budget_per_min
            safety = int(limit * self._config.rate_limit_safety_pct)
            
            # Check if we have budget
            if self._used_weight + weight > safety:
                # Calculate sleep time
                now = time.time()
                reset_time = self._window_start + 60.0
                sleep_sec = max(0.1, reset_time - now)
                
                # Emit throttle
                if self._telemetry:
                    self._telemetry.emit_rate_limit_throttle(int(sleep_sec * 1000), endpoint)
                
                print(f"[GOVERNOR] Throttling for {sleep_sec:.2f}s (Used: {self._used_weight}, Weight: {weight})")
                await asyncio.sleep(sleep_sec)
                
                # After sleep, reset window happens naturally on next acquire or forced here?
                # We should force reset since we slept past window
                self._window_start = time.time()
                self._used_weight = 0
                
            self._used_weight += weight
            
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
            "used": self._used_weight,
            "window_start": self._window_start,
            "budget": self._config.rate_limit_budget_per_min
        }
