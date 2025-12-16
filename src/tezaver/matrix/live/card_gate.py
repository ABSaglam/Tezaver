"""
Card Governance Module for Matrix Live.

Implements staleness and drift gates for strategy cards:
- Staleness: Check card_build_ts age against max_age_hours
- Drift: Track in_card_window pass rate over sliding window
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json


@dataclass
class CardGateConfig:
    """Configuration for card gate."""
    enabled: bool = True
    max_age_hours: float = 72.0
    enforce_mode: str = "BLOCK"  # WARN / BLOCK
    drift_window_bars: int = 20
    min_pass_rate: float = 0.20
    # Test injection flags
    force_stale: bool = False
    force_drift: bool = False


@dataclass
class CardGateResult:
    """Result of card gate evaluation."""
    gate: str = "NA"  # PASS / WARN / BLOCK / NA
    allow: bool = True
    violations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "allow": self.allow,
            "violations": self.violations,
            "metrics": self.metrics,
        }


class CardGate:
    """
    Card governance gate for staleness and drift detection.
    
    Features:
    - Staleness: Blocks/warns if card is older than max_age_hours
    - Drift: Tracks in_card_window pass rate over sliding window
    """
    
    CARD_PATHS = [
        "data/coin_profiles/{symbol}/{timeframe}/sniper_strategy_card_v1.json",
        "data/ai_datasets/{symbol}/{timeframe}/sniper_strategy_card_v1.json",
    ]
    
    def __init__(
        self,
        config: Optional[CardGateConfig] = None,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self._config = config or CardGateConfig()
        self._event_sink = event_sink
        
        # Per-cell drift tracking: cell_id -> deque of bools (in_card_window history)
        self._drift_history: Dict[str, deque] = {}
        
        # Last result per cell
        self._last_results: Dict[str, CardGateResult] = {}
    
    @property
    def config(self) -> CardGateConfig:
        return self._config
    
    @property
    def last_results(self) -> Dict[str, CardGateResult]:
        return self._last_results.copy()
    
    def _emit(self, event: Dict[str, Any]) -> None:
        """Emit telemetry event."""
        if self._event_sink:
            event.setdefault("ts", datetime.now(timezone.utc).isoformat())
            self._event_sink(event)
    
    def _load_card(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """Load card from disk."""
        for path_template in self.CARD_PATHS:
            path = Path(path_template.format(symbol=symbol, timeframe=timeframe))
            if path.exists():
                try:
                    with open(path, "r") as f:
                        return json.load(f)
                except Exception:
                    pass
        return None
    
    def _get_card_age_hours(self, card: Dict[str, Any]) -> Optional[float]:
        """Get card age in hours from card_build_ts or built_at field."""
        # Try common timestamp field names
        ts_str = card.get("card_build_ts") or card.get("built_at") or card.get("created_at")
        if ts_str:
            try:
                build_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta = now - build_dt
                return delta.total_seconds() / 3600.0
            except Exception:
                pass
        return None
    
    def record_tick(self, cell_id: str, in_card_window: bool) -> None:
        """Record in_card_window for drift tracking."""
        if cell_id not in self._drift_history:
            self._drift_history[cell_id] = deque(maxlen=self._config.drift_window_bars)
        self._drift_history[cell_id].append(in_card_window)
    
    def get_pass_rate(self, cell_id: str) -> float:
        """Get current pass rate for cell."""
        if cell_id not in self._drift_history:
            return 1.0  # No history = assume OK
        history = self._drift_history[cell_id]
        if not history:
            return 1.0
        return sum(history) / len(history)
    
    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        profile_id: str,
        cell_id: str,
        open_rule_mode: str,
        cycle_idx: Optional[int] = None,
        in_card_window: Optional[bool] = None,
    ) -> CardGateResult:
        """
        Evaluate card gate.
        
        Returns CardGateResult with gate status and violations.
        """
        result = CardGateResult()
        
        # If not enabled or not CARD_* mode, return NA
        if not self._config.enabled:
            result.gate = "NA"
            result.metrics = {"reason": "GATE_DISABLED"}
            return result
        
        if not open_rule_mode.startswith("CARD_"):
            result.gate = "NA"
            result.metrics = {"reason": f"MODE_{open_rule_mode}_NOT_CARD"}
            return result
        
        # Record tick if in_card_window provided
        if in_card_window is not None:
            self.record_tick(cell_id, in_card_window)
        
        # Load card
        card = self._load_card(symbol, timeframe)
        has_card = card is not None
        
        # Initialize metrics
        age_hours = None
        pass_rate = self.get_pass_rate(cell_id)
        drifted = False
        
        # --- Staleness check ---
        if not has_card:
            result.violations.append("CARD_NOT_FOUND")
        elif self._config.force_stale:
            # Force stale for testing
            age_hours = 9999.0
            result.violations.append("STALE_FORCED")
        else:
            age_hours = self._get_card_age_hours(card)
            if age_hours is None:
                result.violations.append("STALE_UNKNOWN")
            elif age_hours > self._config.max_age_hours:
                result.violations.append(f"STALE_AGE_{age_hours:.1f}h>max_{self._config.max_age_hours}h")
        
        # --- Drift check ---
        if self._config.force_drift:
            # Force drift for testing
            pass_rate = 0.0
            drifted = True
            result.violations.append("DRIFT_FORCED")
        else:
            if pass_rate < self._config.min_pass_rate:
                drifted = True
                result.violations.append(f"DRIFT_LOW_PASSRATE_{pass_rate:.2f}<min_{self._config.min_pass_rate}")
        
        # --- Determine gate status ---
        if result.violations:
            if self._config.enforce_mode == "BLOCK":
                result.gate = "BLOCK"
                result.allow = False
            else:
                result.gate = "WARN"
                result.allow = True  # Allow with warning
        else:
            result.gate = "PASS"
            result.allow = True
        
        # Build metrics
        result.metrics = {
            "has_card": has_card,
            "age_hours": age_hours,
            "max_age_hours": self._config.max_age_hours,
            "card_build_ts": card.get("card_build_ts") or card.get("built_at") if card else None,
            "pass_rate": round(pass_rate, 3),
            "window_bars": self._config.drift_window_bars,
            "min_pass_rate": self._config.min_pass_rate,
            "drifted": drifted,
            "enforce_mode": self._config.enforce_mode,
            "force_stale": self._config.force_stale,
            "force_drift": self._config.force_drift,
        }
        
        # Emit telemetry
        self._emit({
            "event_type": "CARD_GATE_EVAL",
            "symbol": symbol,
            "timeframe": timeframe,
            "cell_id": cell_id,
            "profile_id": profile_id,
            "cycle_idx": cycle_idx,
            "gate": result.gate,
            "allow": result.allow,
            "violations": result.violations,
            "metrics": result.metrics,
        })
        
        # Store result
        self._last_results[cell_id] = result
        
        return result
