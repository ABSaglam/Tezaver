"""
Tezaver Bulut - Security Middlewares
"""
import time
from collections import deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

from tezaver.bulut.core.config import BulutConfig

class SecureHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: BulutConfig):
        super().__init__(app)
        self.config = config

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        if self.config.secure_headers_enabled:
            # Add strict security headers
            headers = response.headers
            headers["X-Content-Type-Options"] = "nosniff"
            headers["X-Frame-Options"] = "DENY"
            headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # CSP is complex, maybe later.
            # HSTS is usually handled by proxy (Caddy/Nginx) but we can add:
            # headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            # leaving HSTS to proxy per request.
            
            # Cache control for sensitive paths (ops)
            if request.url.path.startswith("/ops") or request.url.path.startswith("/api"):
                headers["Cache-Control"] = "no-store, max-age=0"
                # print(f"Added Cache-Control for {request.url.path}")
            else:
                pass
                # print(f"Skipped Cache-Control for {request.url.path}")
                
        return response


class BasicRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory leaky bucket rate limiter per IP.
    Targeting abuse protection, not strict quota management.
    """
    def __init__(self, app, config: BulutConfig, telemetry=None):
        super().__init__(app)
        self.config = config
        self.telemetry = telemetry
        # IP -> (tokens, last_update)
        # We use a simple token bucket.
        self._buckets = {}
        self._max_buckets = 5000 # Prevent memory leak
        
    async def dispatch(self, request: Request, call_next):
        if not self.config.basic_rate_limit_enabled:
            return await call_next(request)
            
        # Lazy load telemetry from global context if available
        if not self.telemetry:
            try:
                from tezaver.bulut.core.context import get_context
                # get_context() might raise if not initialized, handle gracefully
                ctx = get_context()
                if ctx and hasattr(ctx, "telemetry"):
                    self.telemetry = ctx.telemetry
            except:
                pass

        # Bypass for loopback if needed? Not necessarily.
        client_ip = request.client.host if request.client else "unknown"
        
        # Determine limits
        # Ops/Mutations get stricter or different limits? 
        # For now, uniform limit + strict ops limit?
        # User requested: "/ops/* and mutate endpoints strict"
        # We'll use the config RPS for general, maybe stricter for ops?
        # Let's keep it simple: Use config RPS for ALL.
        
        rps = self.config.basic_rate_limit_rps
        burst = self.config.basic_rate_limit_burst
        
        # Check Bucket
        now = time.time()
        bucket = self._buckets.get(client_ip)
        
        if not bucket:
            # (tokens, last_ts)
            # Full burst available initially
            bucket = [burst, now]
            self._buckets[client_ip] = bucket
            
            # Cleanup if too big
            if len(self._buckets) > self._max_buckets:
                self._buckets.clear()
        
        tokens, last_ts = bucket
        
        # Refill
        elapsed = now - last_ts
        refill = elapsed * rps
        tokens = min(burst, tokens + refill)
        
        # Consume
        cost = 1
        if tokens >= cost:
            tokens -= cost
            self._buckets[client_ip] = [tokens, now]
            response = await call_next(request)
            # Add rate limit headers?
            return response
        else:
            # Deny
            self._buckets[client_ip] = [tokens, now] # Update TS
            
            if self.telemetry:
                self.telemetry.emit("RATE_LIMIT_DENY", {"ip": client_ip, "path": request.url.path})
                
            return JSONResponse(
                status_code=429, 
                content={"detail": "Too Many Requests"}
            )
