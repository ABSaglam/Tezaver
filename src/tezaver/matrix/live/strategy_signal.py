# Strategy Signal Adapter
"""
Strategy signal interface and V1 adapter for live trading.

V1 Logic:
- OPEN_LONG: Always trigger on first tick (for testing policy cycle)
- CLOSE_LONG: Policy-driven (HOLD_NEXT_CLOSED handles timing)
- Position guard: LONG → ignore OPEN_LONG, FLAT → ignore CLOSE_LONG
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, Callable


class Signal(Enum):
    """Strategy signal types."""
    NONE = "NONE"
    OPEN_LONG = "OPEN_LONG"
    CLOSE_LONG = "CLOSE_LONG"


class PositionState(Enum):
    """Per-cell position state."""
    FLAT = "FLAT"
    LONG = "LONG"


@dataclass
class CellPosition:
    """Position state for a single cell (symbol/timeframe/profile)."""
    state: PositionState = PositionState.FLAT
    open_order_id: Optional[str] = None
    close_order_id: Optional[str] = None
    open_bar_close_ts: Optional[str] = None
    close_bar_close_ts: Optional[str] = None
    open_ts: Optional[str] = None
    close_ts: Optional[str] = None
    last_fingerprint: Optional[str] = None
    qty: float = 0.0


class PositionStateStore:
    """
    Tracks position state per cell.
    
    Cell key: symbol|tf|profile_id
    """
    
    def __init__(self, event_sink: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.event_sink = event_sink
        self._positions: Dict[str, CellPosition] = {}
    
    def _cell_key(self, symbol: str, tf: str, profile_id: str) -> str:
        return f"{symbol}|{tf}|{profile_id}"
    
    def get(self, symbol: str, tf: str, profile_id: str) -> CellPosition:
        """Get or create position for cell."""
        key = self._cell_key(symbol, tf, profile_id)
        if key not in self._positions:
            self._positions[key] = CellPosition()
        return self._positions[key]
    
    def set_open(self, symbol: str, tf: str, profile_id: str, 
                 order_id: str, bar_close_ts: str, qty: float = 0.0) -> None:
        """Record OPEN order."""
        pos = self.get(symbol, tf, profile_id)
        pos.state = PositionState.LONG
        pos.open_order_id = order_id
        pos.open_bar_close_ts = bar_close_ts
        pos.open_ts = datetime.now(timezone.utc).isoformat()
        pos.qty = qty
        pos.last_fingerprint = f"{symbol}|{tf}|{profile_id}|{bar_close_ts}|OPEN"
        
        if self.event_sink:
            self.event_sink({
                "ts": pos.open_ts,
                "event_type": "POSITION_OPEN",
                "symbol": symbol,
                "timeframe": tf,
                "profile_id": profile_id,
                "order_id": order_id,
                "bar_close_ts": bar_close_ts,
                "qty": qty,
            })
    
    def set_close(self, symbol: str, tf: str, profile_id: str,
                  order_id: str, bar_close_ts: str) -> None:
        """Record CLOSE order."""
        pos = self.get(symbol, tf, profile_id)
        pos.state = PositionState.FLAT
        pos.close_order_id = order_id
        pos.close_bar_close_ts = bar_close_ts
        pos.close_ts = datetime.now(timezone.utc).isoformat()
        pos.last_fingerprint = f"{symbol}|{tf}|{profile_id}|{bar_close_ts}|CLOSE"
        
        if self.event_sink:
            self.event_sink({
                "ts": pos.close_ts,
                "event_type": "POSITION_CLOSE",
                "symbol": symbol,
                "timeframe": tf,
                "profile_id": profile_id,
                "order_id": order_id,
                "bar_close_ts": bar_close_ts,
            })
    
    def is_duplicate(self, symbol: str, tf: str, profile_id: str,
                     bar_close_ts: str, action: str) -> bool:
        """Check if action on this bar is duplicate."""
        pos = self.get(symbol, tf, profile_id)
        fp = f"{symbol}|{tf}|{profile_id}|{bar_close_ts}|{action}"
        return pos.last_fingerprint == fp
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all positions for UI."""
        result = {}
        for key, pos in self._positions.items():
            result[key] = {
                "state": pos.state.value,
                "open_order_id": pos.open_order_id,
                "close_order_id": pos.close_order_id,
                "open_ts": pos.open_ts,
                "close_ts": pos.close_ts,
                "qty": pos.qty,
            }
        return result


class OpenRuleMode(Enum):
    """Strategy open rule modes."""
    ALWAYS_OFF = "ALWAYS_OFF"
    CARD_STRICT_WINDOW = "CARD_STRICT_WINDOW"
    CARD_SOURCE_WINDOW = "CARD_SOURCE_WINDOW"
    AUTO_OPEN_FLAT = "AUTO_OPEN_FLAT"  # V1 compatibility


class StrategySignalAdapter:
    """
    V2 Strategy Signal Adapter.
    
    Prod-safe defaults:
    - auto_open_on_flat: False (must be explicitly enabled)
    - open_rule_mode: ALWAYS_OFF (no opens by default)
    - min_bars_between_actions: 1 (cooldown between actions)
    
    Logic:
    - ALWAYS_OFF → never OPEN_LONG
    - CARD_*_WINDOW → evaluate snapshot against filter window
    - AUTO_OPEN_FLAT → V1 behavior for testing
    """
    
    def __init__(
        self,
        position_store: PositionStateStore,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        # V2: Prod-safe defaults
        auto_open_on_flat: bool = False,
        open_rule_mode: str = "ALWAYS_OFF",  # ALWAYS_OFF / CARD_STRICT_WINDOW / CARD_SOURCE_WINDOW / AUTO_OPEN_FLAT
        min_bars_between_actions: int = 1,
        # V3: Contract gating
        contract_enforce: str = "WARN",  # WARN / BLOCK
        profile_id: str = "SILVER_15m",  # Profile for filter windows
        # V4: Close rule mode
        close_rule_mode: str = "ALWAYS_OFF",  # ALWAYS_OFF / CLOSE_ON_NEXT_SIGNAL
    ):
        self.position_store = position_store
        self.event_sink = event_sink
        self.auto_open_on_flat = auto_open_on_flat
        self.open_rule_mode = open_rule_mode
        self.min_bars_between_actions = min_bars_between_actions
        self.contract_enforce = contract_enforce
        self.profile_id = profile_id
        self.close_rule_mode = close_rule_mode
        
        self._opened_cells: set = set()  # Track cells that have opened (for single-cycle test)
        self._long_cells: set = set()  # Track cells currently in LONG position
        self._last_action_bar_ts: Dict[str, str] = {}  # Cooldown tracking
        self._cooldown_remaining: Dict[str, int] = {}  # Bars remaining per cell
    
    def _check_cooldown(self, cell_key: str, bar_close_ts: str) -> bool:
        """Check if cooldown has passed since last action."""
        last_ts = self._last_action_bar_ts.get(cell_key)
        if last_ts is None:
            return True
        # Simple comparison - bar_close_ts is ISO format, lexicographic comparison works
        return bar_close_ts > last_ts
    
    def _record_action(self, cell_key: str, bar_close_ts: str) -> None:
        """Record action for cooldown tracking."""
        self._last_action_bar_ts[cell_key] = bar_close_ts
    
    def _evaluate_card_window(
        self,
        snapshot: Optional[Dict[str, Any]],
        mode: str,
        symbol: str = "",
        tf: str = "",
    ) -> tuple[bool, bool, Dict[str, Any]]:
        """
        Evaluate snapshot against card filter window.
        
        CARD_SOURCE_WINDOW: provenance filters_used thresholds kontrolü
        CARD_STRICT_WINDOW: strict_selection_details distance hesaplama
        
        Returns: (passed_filters, blocked_by_contract, filter_result)
        """
        if snapshot is None:
            return False, False, {"reason": "NO_SNAPSHOT", "in_card_window": False}
        
        # Extract snapshot features
        rsi = snapshot.get("rsi")
        volume_rel = snapshot.get("volume_rel")
        atr_pct = snapshot.get("atr_pct")
        close_price = snapshot.get("close")
        quality = snapshot.get("quality", 50.0)  # default quality if not available
        
        filter_result = {
            "close": close_price,
            "rsi": rsi,
            "atr_pct": atr_pct,
            "volume_rel": volume_rel,
            "quality": quality,
            "in_card_window": False,
            "card_mode": mode,
            "card_source_count": 0,
            "card_strict_count": 0,
            "passed_filters": False,
            "distance": None,
        }
        
        try:
            from pathlib import Path
            import json
            
            # Determine card path
            card_path = Path("data") / "coin_profiles" / symbol / tf / "sniper_strategy_card_v1.json"
            if not card_path.exists():
                card_path = Path("data") / "ai_datasets" / symbol / tf / "sniper_strategy_card_v1.json"
            
            if not card_path.exists():
                filter_result["reason"] = "CARD_NOT_FOUND"
                filter_result["card_path"] = str(card_path)
                return False, False, filter_result
            
            # Load card
            with open(card_path) as f:
                card_data = json.load(f)
            
            provenance = card_data.get("provenance", {})
            filters_used = provenance.get("filters_used", {})
            entry_windows = filters_used.get("entry_windows", {})
            
            # Count entries
            source_ids = card_data.get("source_trade_ids", [])
            strict_ids = card_data.get("strict_trade_ids", [])
            filter_result["card_source_count"] = len(source_ids)
            filter_result["card_strict_count"] = len(strict_ids)
            filter_result["card_ids_count"] = len(source_ids) if mode == "CARD_SOURCE_WINDOW" else len(strict_ids)
            
            # ========== CARD_SOURCE_WINDOW: threshold check ==========
            if mode == "CARD_SOURCE_WINDOW":
                passed = True
                fail_reasons = []
                
                # RSI check
                rsi_range = entry_windows.get("rsi", {})
                if rsi is not None and rsi_range:
                    rsi_min = rsi_range.get("min", 0)
                    rsi_max = rsi_range.get("max", 100)
                    if not (rsi_min <= rsi <= rsi_max):
                        passed = False
                        fail_reasons.append(f"rsi={rsi:.1f} not in [{rsi_min}, {rsi_max}]")
                
                # Volume check
                vol_range = entry_windows.get("volume_rel", {})
                if volume_rel is not None and vol_range:
                    vol_min = vol_range.get("min", 0)
                    vol_max = vol_range.get("max", 10)
                    if not (vol_min <= volume_rel <= vol_max):
                        passed = False
                        fail_reasons.append(f"volume_rel={volume_rel:.2f} not in [{vol_min}, {vol_max}]")
                
                # ATR check
                atr_range = entry_windows.get("atr_pct", {})
                if atr_pct is not None and atr_range:
                    atr_min = atr_range.get("min", 0)
                    atr_max = atr_range.get("max", 5)
                    if not (atr_min <= atr_pct <= atr_max):
                        passed = False
                        fail_reasons.append(f"atr_pct={atr_pct:.3f} not in [{atr_min}, {atr_max}]")
                
                filter_result["in_card_window"] = passed
                filter_result["passed_filters"] = passed
                filter_result["reason"] = "CARD_SOURCE_PASSED" if passed else "CARD_SOURCE_FAILED"
                if fail_reasons:
                    filter_result["fail_reasons"] = fail_reasons
            
            # ========== CARD_STRICT_WINDOW: distance check ==========
            elif mode == "CARD_STRICT_WINDOW":
                strict_details = provenance.get("strict_selection_details", {})
                centroid = strict_details.get("centroid", {})
                std_devs = strict_details.get("std_devs", {})
                distance_cutoff = strict_details.get("distance_cutoff", 2.0)
                
                if not centroid:
                    # No strict details - fall back to source window logic
                    filter_result["reason"] = "NO_STRICT_DETAILS"
                    filter_result["in_card_window"] = len(strict_ids) > 0
                    filter_result["passed_filters"] = len(strict_ids) > 0
                else:
                    # Calculate weighted L2 distance
                    distance_sq = 0.0
                    feature_count = 0
                    
                    for feature_name, centroid_val in centroid.items():
                        snapshot_val = snapshot.get(feature_name)
                        if snapshot_val is not None:
                            std_val = std_devs.get(feature_name, 1.0)
                            if std_val > 0:
                                z_score = (snapshot_val - centroid_val) / std_val
                                distance_sq += z_score ** 2
                                feature_count += 1
                    
                    if feature_count > 0:
                        distance = (distance_sq / feature_count) ** 0.5
                        filter_result["distance"] = round(distance, 4)
                        
                        passed = distance <= distance_cutoff
                        filter_result["in_card_window"] = passed
                        filter_result["passed_filters"] = passed
                        filter_result["distance_cutoff"] = distance_cutoff
                        filter_result["reason"] = "CARD_STRICT_PASSED" if passed else "CARD_STRICT_FAILED"
                    else:
                        filter_result["reason"] = "NO_FEATURES_FOR_DISTANCE"
                        filter_result["in_card_window"] = False
                        filter_result["passed_filters"] = False
            
            # ========== Contract check ==========
            blocked = False
            from tezaver.sniper.v4.select_v4 import load_card_contract_state
            contract_state = load_card_contract_state(symbol, tf, card_path)
            if contract_state.get("available") and self.contract_enforce == "BLOCK":
                if not contract_state.get("ok", True):
                    blocked = True
                    filter_result["contract_violations"] = contract_state.get("violations", [])
                    filter_result["reason"] = "CONTRACT_BLOCKED"
            
            return filter_result.get("passed_filters", False), blocked, filter_result
            
        except FileNotFoundError:
            filter_result["reason"] = "CARD_NOT_FOUND"
            return False, False, filter_result
        except Exception as e:
            filter_result["reason"] = f"CARD_ERROR: {e}"
            return False, False, filter_result
    
    def compute_signal(
        self,
        symbol: str,
        tf: str,
        profile_id: str,
        bar_close_ts: str,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> Signal:
        """
        Compute signal for this tick.
        
        V2 Logic:
        - ALWAYS_OFF: never OPEN_LONG
        - CARD_*_WINDOW: evaluate filter window
        - AUTO_OPEN_FLAT / auto_open_on_flat: open on first FLAT tick
        """
        # 1. Defaults
        signal = Signal.NONE
        reason = "NONE"
        passed_filters = False
        blocked_by_contract = False
        in_card_window = False
        filter_result: Optional[Dict[str, Any]] = None
        
        cell_key = self._cell_key(symbol, tf, profile_id)
        
        # 2. Check position
        pos = self.position_store.get(symbol, tf, profile_id)
        is_flat = (pos.state == PositionState.FLAT)
        
        # 3. Evaluate OPEN Logic (if Flat)
        if is_flat:
            # A) Auto Open (for testing)
            if self.open_rule_mode == OpenRuleMode.AUTO_OPEN_FLAT or self.auto_open_on_flat:
                # Check cooldown
                if self._check_cooldown(cell_key, bar_close_ts):
                    signal = Signal.OPEN_LONG
                    reason = "AUTO_OPEN"
                    passed_filters = True
                else:
                    reason = "COOLDOWN"
            
            # B) Card Window (Production logic)
            elif self.open_rule_mode in (OpenRuleMode.CARD_SOURCE_WINDOW, OpenRuleMode.CARD_STRICT_WINDOW):
                passed, blocked_contract, res = self._evaluate_card_window(
                    snapshot, 
                    self.open_rule_mode, 
                    symbol=symbol, 
                    tf=tf
                )
                filter_result = res
                blocked_by_contract = blocked_contract
                
                if blocked_contract:
                    reason = "CONTRACT_BLOCK"
                elif passed:
                    if self._check_cooldown(cell_key, bar_close_ts):
                        signal = Signal.OPEN_LONG
                        reason = "CARD_PASS"
                        passed_filters = True
                        in_card_window = True
                    else:
                        reason = "COOLDOWN"
                else:
                    reason = "FILTER_FAIL"
                    
            # C) ALWAYS_OFF
            else:
                reason = "ALWAYS_OFF"
        
        # 4. Evaluate CLOSE Logic (if Long)
        else: # is LONG
            # V4: CLOSE_ON_NEXT_SIGNAL
            if self.close_rule_mode == "CLOSE_ON_NEXT_SIGNAL":
                signal = Signal.CLOSE_LONG
                reason = "CLOSE_RULE_TEST"
            else:
                reason = "HOLDING"
        
        # 5. Emit STRATEGY_SIGNAL
        cooldown_ok = self._check_cooldown(cell_key, bar_close_ts)
        
        # Emit if signal present OR significant reason
        if signal != Signal.NONE or reason in ["FILTER_FAIL", "CONTRACT_BLOCK", "COOLDOWN", "AUTO_OPEN", "CARD_PASS"]:
            
            # Record action if OPEN/CLOSE (state change)
            if signal == Signal.OPEN_LONG:
                self._record_action(cell_key, bar_close_ts)
                self._opened_cells.add(cell_key)
                self._long_cells.add(cell_key)
            elif signal == Signal.CLOSE_LONG:
                self._record_action(cell_key, bar_close_ts)
                self._long_cells.discard(cell_key)

            self._emit_signal_event(
                symbol, tf, profile_id, bar_close_ts, snapshot,
                signal=signal,
                reason=reason,
                passed_filters=passed_filters,
                blocked_by_contract=blocked_by_contract,
                cooldown_ok=cooldown_ok,
                filter_result=filter_result
            )
            
        return signal
    
    def _emit_signal_event(
        self,
        symbol: str,
        tf: str,
        profile_id: str,
        bar_close_ts: str,
        snapshot: Optional[Dict[str, Any]],
        signal: Signal,
        reason: str,
        passed_filters: bool,
        blocked_by_contract: bool,
        cooldown_ok: bool,
        filter_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit STRATEGY_SIGNAL telemetry event."""
        if self.event_sink:
            cell_id = f"{symbol}|{tf}|{profile_id}"
            
            # Extract CARD fields from filter_result
            in_card_window = filter_result.get("in_card_window", False) if filter_result else False
            card_mode = filter_result.get("card_mode", "N/A") if filter_result else "N/A"
            card_ids_count = filter_result.get("card_ids_count", 0) if filter_result else 0
            card_source_count = filter_result.get("card_source_count", 0) if filter_result else 0
            card_strict_count = filter_result.get("card_strict_count", 0) if filter_result else 0
            contract_violations = filter_result.get("contract_violations", []) if filter_result else []
            
            event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event_type": "STRATEGY_SIGNAL",
                # Mandatory fields
                "symbol": symbol,
                "timeframe": tf,
                "cell_id": cell_id,
                "profile_id": profile_id,
                "bar_close_ts": bar_close_ts,
                "signal": signal.value,
                "open_rule_mode": self.open_rule_mode,
                "reason": reason,
                "passed_filters": passed_filters,
                # CARD fields
                "in_card_window": in_card_window,
                "card_mode": card_mode,
                "card_ids_count": card_ids_count,
                "card_source_count": card_source_count,
                "card_strict_count": card_strict_count,
                # Contract fields
                "contract_enforce": self.contract_enforce,
                "blocked_by_contract": blocked_by_contract,
                "contract_violations": contract_violations,
                # Cooldown fields
                "cooldown_ok": cooldown_ok,
                "cooldown_remaining": self._cooldown_remaining.get(cell_id, 0),
                # Profile fields
                "configured_profile_id": self.profile_id,
            }
            
            # Add snapshot key fields
            if snapshot:
                event["close"] = snapshot.get("close")
                event["rsi"] = snapshot.get("rsi")
                event["atr_pct"] = snapshot.get("atr_pct")
                event["volume_rel"] = snapshot.get("volume_rel")
            
            if filter_result:
                event["filter_result"] = filter_result
            
            self.event_sink(event)
    
    def reset_cell(self, symbol: str, tf: str, profile_id: str) -> None:
        """Reset cell for new cycle (after CLOSE)."""
        cell_key = f"{symbol}|{tf}|{profile_id}"
        self._opened_cells.discard(cell_key)

