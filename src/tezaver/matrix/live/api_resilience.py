import time
import random
import logging
from enum import Enum, auto
from typing import Callable, Any, Dict, Optional, List
import requests

class ErrorClass(Enum):
    NONE = auto()
    RATE_LIMIT = auto()    # 429
    TRANSIENT = auto()     # 5xx, timeouts, conn errors
    FATAL = auto()         # 400, 401, 403, 404 (non-retryable)

class CircuitState(Enum):
    CLOSED = auto()   # Normal
    OPEN = auto()     # Blocking
    HALF_OPEN = auto() # Testing

class ApiResilienceManager:
    def __init__(self, 
                 run_id: str, 
                 emit_fn: Optional[Callable] = None,
                 max_retries: int = 3,
                 circuit_threshold: int = 5,
                 cool_down_s: int = 60):
        self.run_id = run_id
        self.emit_fn = emit_fn
        self.max_retries = max_retries
        self.circuit_threshold = circuit_threshold
        self.cool_down_s = cool_down_s
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_ts = 0.0
        
        # Stats
        self.stats = {
            "total_calls": 0,
            "rate_limit_count": 0,
            "transient_count": 0,
            "fatal_count": 0,
            "retries_count": 0,
            "circuit_trips": 0
        }

    def classify_error(self, exc: Exception) -> ErrorClass:
        if isinstance(exc, requests.exceptions.HTTPError):
            status_code = exc.response.status_code
            if status_code == 429:
                return ErrorClass.RATE_LIMIT
            elif status_code >= 500:
                return ErrorClass.TRANSIENT
            else:
                return ErrorClass.FATAL
        elif isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return ErrorClass.TRANSIENT
        return ErrorClass.FATAL

    def _get_backoff(self, attempt: int) -> float:
        # Exponential backoff: 1s, 2s, 4s... + jitter
        base = 2 ** attempt
        jitter = random.uniform(0, 0.5)
        return base + jitter

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        self.stats["total_calls"] += 1
        
        # 1. Circuit Breaker Check
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_ts > self.cool_down_s:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"CIRCUIT_BREAKER_OPEN: Blocking call to {fn.__name__}")

        attempt = 0
        while attempt <= self.max_retries:
            try:
                result = fn(*args, **kwargs)
                
                # Success
                if self.state == CircuitState.HALF_OPEN:
                    self._close_circuit()
                else:
                    self.failure_count = max(0, self.failure_count - 1)
                
                if self.emit_fn:
                    self.emit_fn("API_CALL_RESULT", {
                        "status": "SUCCESS",
                        "attempt": attempt
                    })
                return result
                
            except Exception as e:
                error_class = self.classify_error(e)
                attempt += 1
                
                # Update stats
                if error_class == ErrorClass.RATE_LIMIT: self.stats["rate_limit_count"] += 1
                elif error_class == ErrorClass.TRANSIENT: self.stats["transient_count"] += 1
                elif error_class == ErrorClass.FATAL: self.stats["fatal_count"] += 1
                
                if attempt > self.max_retries or error_class == ErrorClass.FATAL:
                    self._handle_failure(e)
                    if self.emit_fn:
                        self.emit_fn("API_CALL_RESULT", {
                            "status": "FAILED",
                            "error_class": error_class.name,
                            "error": str(e),
                            "attempt": attempt
                        })
                    raise e
                
                # Retryable
                self.stats["retries_count"] += 1
                wait_s = self._get_backoff(attempt)
                if error_class == ErrorClass.RATE_LIMIT:
                    wait_s *= 2 # Extra cautious for rate limits
                
                if self.emit_fn:
                    self.emit_fn("RETRY_SCHEDULED", {
                        "error_class": error_class.name,
                        "attempt": attempt,
                        "wait_s": wait_s
                    })
                
                time.sleep(wait_s)

    def _handle_failure(self, e: Exception):
        self.failure_count += 1
        self.last_failure_ts = time.time()
        
        if self.failure_count >= self.circuit_threshold and self.state != CircuitState.OPEN:
            self._trip_circuit()

    def _trip_circuit(self):
        self.state = CircuitState.OPEN
        self.stats["circuit_trips"] += 1
        if self.emit_fn:
            self.emit_fn("CIRCUIT_OPEN", {
                "failure_count": self.failure_count,
                "cool_down_s": self.cool_down_s
            })

    def _close_circuit(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        if self.emit_fn:
            self.emit_fn("CIRCUIT_CLOSE", {})

    def get_summary(self) -> Dict:
        return {
            **self.stats,
            "circuit_state": self.state.name,
            "last_failure_ts": self.last_failure_ts,
            "run_id": self.run_id
        }
