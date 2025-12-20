# Matrix V2 Silver Core Strategy
"""
Silver strategy configuration, analyzer, and strategist for Matrix v2.

This module provides the adapter layer between Coin Lab's Silver strategy cards
and Matrix's trading engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import uuid

from tezaver.matrix.core.engine import IAnalyzer, IStrategist
from tezaver.matrix.core.types import MarketSignal, TradeDecision
from tezaver.matrix.core.account import AccountState
from tezaver.matrix.core.profile import MatrixCellProfile
from tezaver.matrix.coin_page.schema import StrategyConfigV1, StrategyRiskContractV1


@dataclass
class SilverStrategyConfig:
    """
    Configuration for Silver strategy loaded from a strategy card.
    """
    symbol: str
    timeframe: str
    
    # Entry filters
    rsi_range: tuple[float, float] | None = None
    volume_rel_range: tuple[float, float] | None = None
    atr_pct_range: tuple[float, float] | None = None
    min_quality_score: Optional[float] = None
    
    # Exit parameters
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None
    max_horizon_bars: Optional[int] = None
    
    # ML-enhanced filters (optional)
    rsi_gap_1d_range: tuple[float, float] | None = None
    atr_pct_15m_range: tuple[float, float] | None = None
    rsi_1h_range: tuple[float, float] | None = None
    
    # Risk contract (from risk_contract_v1)
    max_risk_per_trade: float | None = None  # Cap from contract, None = no cap
    
    metadata: dict[str, object] = field(default_factory=dict)


# ============================================================================
# Tightness V2: Dataset Stats and Interpolation
# ============================================================================

@dataclass
class SilverDatasetStats:
    """Statistics from pattern dataset for tightness interpolation."""
    rsi_15m_min: float
    rsi_15m_max: float
    volume_rel_15m_min: float
    volume_rel_15m_max: float
    atr_pct_15m_min: float
    atr_pct_15m_max: float
    rsi_gap_1d_min: Optional[float] = None
    rsi_gap_1d_max: Optional[float] = None
    rsi_1h_min: Optional[float] = None
    rsi_1h_max: Optional[float] = None


@dataclass
class SilverFilterWindow:
    """Effective filter window after tightness interpolation."""
    tightness: float
    rsi_15m_range: tuple[float, float]
    volume_rel_range: tuple[float, float]
    atr_pct_range: tuple[float, float]
    ml_enabled: bool
    rsi_gap_1d_range: Optional[tuple[float, float]] = None
    rsi_1h_range: Optional[tuple[float, float]] = None
    quality_min: float = 60.0


def _interpolate_interval(
    global_min: float,
    global_max: float,
    card_min: float,
    card_max: float,
    tightness: float,
) -> tuple[float, float]:
    """
    Interpolate between global and card range based on tightness.
    
    tightness=100 → card range
    tightness=0   → global range
    tightness=50  → midpoint
    """
    alpha = max(0.0, min(1.0, tightness / 100.0))
    eff_min = global_min * (1 - alpha) + card_min * alpha
    eff_max = global_max * (1 - alpha) + card_max * alpha
    return (eff_min, eff_max)


def build_silver_filter_window(
    cfg: SilverStrategyConfig,
    stats: SilverDatasetStats,
    tightness: float,
) -> SilverFilterWindow:
    """
    Build effective filter window from card + dataset stats + tightness.
    
    Entry filters: Linear interpolation between global and card.
    ML filters:
      - tight >= 70: card range
      - 40 <= tight < 70: interpolation
      - tight < 40: disabled
    """
    # Entry filters interpolation
    rsi_range = _interpolate_interval(
        stats.rsi_15m_min, stats.rsi_15m_max,
        cfg.rsi_range[0] if cfg.rsi_range else stats.rsi_15m_min,
        cfg.rsi_range[1] if cfg.rsi_range else stats.rsi_15m_max,
        tightness,
    )
    
    volume_range = _interpolate_interval(
        stats.volume_rel_15m_min, stats.volume_rel_15m_max,
        cfg.volume_rel_range[0] if cfg.volume_rel_range else stats.volume_rel_15m_min,
        cfg.volume_rel_range[1] if cfg.volume_rel_range else stats.volume_rel_15m_max,
        tightness,
    )
    
    atr_range = _interpolate_interval(
        stats.atr_pct_15m_min, stats.atr_pct_15m_max,
        cfg.atr_pct_range[0] if cfg.atr_pct_range else stats.atr_pct_15m_min,
        cfg.atr_pct_range[1] if cfg.atr_pct_range else stats.atr_pct_15m_max,
        tightness,
    )
    
    # ML filters: tiered policy
    ml_enabled = tightness >= 40
    rsi_gap_1d_range: Optional[tuple[float, float]] = None
    rsi_1h_range: Optional[tuple[float, float]] = None
    
    if ml_enabled and stats.rsi_gap_1d_min is not None:
        if tightness >= 70:
            # Full card range
            if cfg.rsi_gap_1d_range:
                rsi_gap_1d_range = cfg.rsi_gap_1d_range
        else:
            # Interpolate (40-70 range)
            ml_alpha = (tightness - 40) / 30.0  # 0 at 40, 1 at 70
            if cfg.rsi_gap_1d_range:
                rsi_gap_1d_range = _interpolate_interval(
                    stats.rsi_gap_1d_min, stats.rsi_gap_1d_max,
                    cfg.rsi_gap_1d_range[0], cfg.rsi_gap_1d_range[1],
                    ml_alpha * 100,
                )
    
    if ml_enabled and stats.rsi_1h_min is not None:
        if tightness >= 70:
            if cfg.rsi_1h_range:
                rsi_1h_range = cfg.rsi_1h_range
        else:
            ml_alpha = (tightness - 40) / 30.0
            if cfg.rsi_1h_range:
                rsi_1h_range = _interpolate_interval(
                    stats.rsi_1h_min, stats.rsi_1h_max,
                    cfg.rsi_1h_range[0], cfg.rsi_1h_range[1],
                    ml_alpha * 100,
                )
    
    return SilverFilterWindow(
        tightness=tightness,
        rsi_15m_range=rsi_range,
        volume_rel_range=volume_range,
        atr_pct_range=atr_range,
        ml_enabled=ml_enabled,
        rsi_gap_1d_range=rsi_gap_1d_range,
        rsi_1h_range=rsi_1h_range,
        quality_min=60.0,  # Core rule always applies
    )


# Legacy helper (kept for backward compatibility)
def _widen_range(
    rng: tuple[float, float] | None,
    widen_factor: float,
) -> tuple[float, float] | None:
    """Widen a min/max range by the given factor around its center."""
    if rng is None:
        return None
    min_val, max_val = rng
    center = (min_val + max_val) / 2.0
    half_range = (max_val - min_val) / 2.0
    new_half = half_range * widen_factor
    return (center - new_half, center + new_half)


def relax_silver_filters_for_experiment(
    cfg: SilverStrategyConfig,
    widen_factor: float,
) -> SilverStrategyConfig:
    """
    Legacy: Relax entry/ML filters for experiment mode.
    Use build_silver_filter_window for v2 tightness.
    """
    from dataclasses import replace
    
    new_rsi_range = _widen_range(cfg.rsi_range, widen_factor)
    new_volume_range = _widen_range(cfg.volume_rel_range, widen_factor)
    new_atr_range = _widen_range(cfg.atr_pct_range, widen_factor)
    new_rsi_gap_1d = _widen_range(cfg.rsi_gap_1d_range, widen_factor)
    new_atr_15m = _widen_range(cfg.atr_pct_15m_range, widen_factor)
    new_rsi_1h = _widen_range(cfg.rsi_1h_range, widen_factor)
    
    new_quality = None
    if cfg.min_quality_score is not None:
        new_quality = cfg.min_quality_score / widen_factor
    
    return replace(
        cfg,
        rsi_range=new_rsi_range,
        volume_rel_range=new_volume_range,
        atr_pct_range=new_atr_range,
        rsi_gap_1d_range=new_rsi_gap_1d,
        atr_pct_15m_range=new_atr_15m,
        rsi_1h_range=new_rsi_1h,
        min_quality_score=new_quality,
    )

def load_silver_strategy_config_from_card(
    card_path: Path,
    symbol: str,
    timeframe: str,
) -> SilverStrategyConfig:
    """
    Load a Silver strategy card JSON produced by Coin Lab and
    convert it into a SilverStrategyConfig usable by Matrix.
    
    Expected JSON structure:
    {
        "version": "v2_ml",
        "entry_filters": {
            "rsi_15m": {"min": 19.7, "max": 28.7},
            "volume_rel_15m": {"min": 2.0, "max": 2.4},
            "atr_pct_15m": {"min": 0.65, "max": 1.82},
            "quality_score": {"min": 60.0}
        },
        "ml_filters": {
            "rsi_gap_1d": {"min": -20.9, "max": 0.0},
            "atr_pct_15m": {"min": 0.71, "max": 1.82},
            "rsi_1h": {"min": 16.5, "max": 35.0}
        },
        "exit": {
            "tp_pct": 0.09,
            "sl_pct": 0.02,
            "max_horizon_bars": 48
        }
    }
    
    Args:
        card_path: Path to the strategy card JSON file.
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Bar timeframe (e.g., "15m").
        
    Returns:
        SilverStrategyConfig instance.
        
    Raises:
        FileNotFoundError: If card_path does not exist.
    """
    if not card_path.exists():
        raise FileNotFoundError(f"Strategy card not found: {card_path}")
    
    with card_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    
    entry = raw.get("entry_filters", {})
    # Also try "filters" key (used in silver_strategy_card_v1.json)
    if not entry:
        entry = raw.get("filters", {})
    ml = raw.get("ml_filters", {})
    exit_cfg = raw.get("exit", {})
    # Also try "risk" key (used in silver_strategy_card_v1.json)
    if not exit_cfg:
        exit_cfg = raw.get("risk", {})
    
    def _to_range(d: dict | None) -> tuple[float, float] | None:
        if not d:
            return None
        if "min" not in d or "max" not in d:
            return None
        # Handle null max
        if d["max"] is None:
            return None
        return float(d["min"]), float(d["max"])
    
    def _get_min_only(d: dict | None) -> float | None:
        if not d or "min" not in d:
            return None
        return float(d["min"])
    
    return SilverStrategyConfig(
        symbol=symbol,
        timeframe=timeframe,
        rsi_range=_to_range(entry.get("rsi_15m")),
        volume_rel_range=_to_range(entry.get("volume_rel_15m")),
        atr_pct_range=_to_range(entry.get("atr_pct_15m")),
        min_quality_score=_get_min_only(entry.get("quality_score")),
        tp_pct=float(exit_cfg["tp_pct"]) if "tp_pct" in exit_cfg else None,
        sl_pct=float(exit_cfg["sl_pct"]) if "sl_pct" in exit_cfg else None,
        max_horizon_bars=int(exit_cfg["max_horizon_bars"]) if "max_horizon_bars" in exit_cfg else None,
        rsi_gap_1d_range=_to_range(ml.get("rsi_gap_1d")),
        atr_pct_15m_range=_to_range(ml.get("atr_pct_15m")),
        rsi_1h_range=_to_range(ml.get("rsi_1h")),
        metadata={"card_version": raw.get("version")},
    )


# =============================================================================
# Profile-Based Loader (CoinPage V2)
# =============================================================================


def load_silver_strategy_config_from_profile(
    profile: MatrixCellProfile,
) -> SilverStrategyConfig:
    """
    Load SilverStrategyConfig from a MatrixCellProfile (CoinPage V2).
    
    This is the preferred loader for Matrix runtime and War Game.
    Config comes from profile.strategy_config (StrategyConfigV1).
    Risk cap comes from profile.risk_contract (StrategyRiskContractV1).
    
    Args:
        profile: MatrixCellProfile loaded from CoinPage V2.
        
    Returns:
        SilverStrategyConfig instance.
        
    Raises:
        ValueError: If profile has no strategy_config.
    """
    if profile.strategy_config is None:
        raise ValueError(f"Silver profile {profile.profile_id} has no strategy config")
    
    s: StrategyConfigV1 = profile.strategy_config
    rc: Optional[StrategyRiskContractV1] = profile.risk_contract
    
    # 1) Entry filters
    entry = s.entry_filters or {}
    ml = s.ml_filters or {}
    
    def _to_range(d: dict | None) -> tuple[float, float] | None:
        if not d:
            return None
        if "min" not in d or "max" not in d:
            return None
        # Handle null max
        if d.get("max") is None:
            return None
        return float(d["min"]), float(d["max"])
    
    def _get_min_only(d: dict | None) -> float | None:
        if not d or "min" not in d:
            return None
        return float(d["min"])
    
    # 2) Exit parameters
    exit_cfg = s.exit or {}
    tp_pct = float(exit_cfg.get("tp_pct", 0.09)) if "tp_pct" in exit_cfg else 0.09
    sl_pct = float(exit_cfg.get("sl_pct", 0.02)) if "sl_pct" in exit_cfg else 0.02
    max_horizon_bars = int(exit_cfg.get("max_horizon_bars", 48)) if "max_horizon_bars" in exit_cfg else 48
    
    # 3) Risk contract (max_risk_per_trade)
    max_risk_per_trade: float | None = None
    if rc is not None:
        max_risk_per_trade = rc.max_risk_per_trade
    
    return SilverStrategyConfig(
        symbol=profile.symbol,
        timeframe=profile.timeframe,
        rsi_range=_to_range(entry.get("rsi_15m")),
        volume_rel_range=_to_range(entry.get("volume_rel_15m")),
        atr_pct_range=_to_range(entry.get("atr_pct_15m")),
        min_quality_score=_get_min_only(entry.get("quality_score")),
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        max_horizon_bars=max_horizon_bars,
        rsi_gap_1d_range=_to_range(ml.get("rsi_gap_1d")),
        atr_pct_15m_range=_to_range(ml.get("atr_pct_15m")),
        rsi_1h_range=_to_range(ml.get("rsi_1h")),
        max_risk_per_trade=max_risk_per_trade,
        metadata={
            "profile_id": profile.profile_id,
            "kind": profile.kind,
            "strategy_version": s.version,
        },
    )


from typing import Optional, Callable, Dict, Any

class SilverAnalyzer(IAnalyzer):
    """
    Silver Analyzer - inspects market snapshots and emits SILVER_ENTRY signals.
    
    This is the first skeleton implementation. It checks basic Silver filters
    and generates signals when conditions are met.
    
    In the future, this will integrate with:
    - Rally detection from Coin Lab
    - ML classifier predictions
    - Multi-timeframe indicators
    """
    
    def __init__(self, cfg: SilverStrategyConfig, event_sink: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """
        Initialize SilverAnalyzer with strategy config.
        
        Args:
            cfg: SilverStrategyConfig loaded from strategy card.
            event_sink: Optional sink for telemetry events.
        """
        self._cfg = cfg
        self.event_sink = event_sink
    
    def _check_range(self, value: float | None, range_tuple: tuple[float, float] | None) -> bool:
        """Check if value is within the given range."""
        if value is None or range_tuple is None:
            return True  # No filter = pass
        lo, hi = range_tuple
        return lo <= value <= hi
    
    def analyze(self, market_snapshot: dict) -> list[MarketSignal]:
        """
        Analyze market snapshot and return SILVER_ENTRY signals if conditions met.
        
        Args:
            market_snapshot: Dict containing OHLCV and indicator data.
                Expected keys: rsi_15m, volume_rel, atr_pct, quality_score, timestamp
                
        Returns:
            List of MarketSignal objects (at most 1 for now).
        """
        signals: list[MarketSignal] = []
        timestamp = market_snapshot.get("timestamp") or market_snapshot.get("ts")
        
        # Extract indicators from snapshot
        rsi_15m = market_snapshot.get("rsi_15m")
        volume_rel = market_snapshot.get("volume_rel")
        atr_pct = market_snapshot.get("atr_pct")
        quality_score = market_snapshot.get("quality_score")
        
        # Check entry filters
        rsi_ok = self._check_range(rsi_15m, self._cfg.rsi_range)
        volume_ok = self._check_range(volume_rel, self._cfg.volume_rel_range)
        atr_ok = self._check_range(atr_pct, self._cfg.atr_pct_range)
        
        # Check quality score (min threshold)
        quality_ok = True
        if self._cfg.min_quality_score is not None and quality_score is not None:
            quality_ok = quality_score >= self._cfg.min_quality_score
        
        # Check ML filters if present
        rsi_gap_1d = market_snapshot.get("rsi_gap_1d")
        atr_pct_15m = market_snapshot.get("atr_pct_15m")
        rsi_1h = market_snapshot.get("rsi_1h")
        
        ml_rsi_gap_ok = self._check_range(rsi_gap_1d, self._cfg.rsi_gap_1d_range)
        ml_atr_ok = self._check_range(atr_pct_15m, self._cfg.atr_pct_15m_range)
        ml_rsi_1h_ok = self._check_range(rsi_1h, self._cfg.rsi_1h_range)
        
        passed_filters = all([rsi_ok, volume_ok, atr_ok, quality_ok, ml_rsi_gap_ok, ml_atr_ok, ml_rsi_1h_ok])
        
        # Emit Telemetry (STRATEGY_SIGNAL)
        if self.event_sink:
            signal_enum = "OPEN_LONG" if passed_filters else "NONE"
            reason = "SILVER_ENTRY" if passed_filters else "FILTER_FAIL"
            
            # Construct detailed reason if failed
            if not passed_filters:
                failures = []
                if not rsi_ok: failures.append("RSI")
                if not volume_ok: failures.append("VOL")
                if not atr_ok: failures.append("ATR")
                if not quality_ok: failures.append("QUAL")
                if not ml_rsi_gap_ok: failures.append("ML_GAP")
                if not ml_atr_ok: failures.append("ML_ATR")
                if not ml_rsi_1h_ok: failures.append("ML_1H")
                if failures:
                    reason = f"FAIL_{'_'.join(failures)}"
            
            ts_iso = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
            
            # Emit only if signal or if specifically debug (optional)
            # For now emit everything to enable "Why NO trade?" analysis in SIM
            self.event_sink({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event_type": "STRATEGY_SIGNAL",
                "symbol": self._cfg.symbol,
                "timeframe": self._cfg.timeframe,
                "cell_id": f"{self._cfg.symbol}|{self._cfg.timeframe}|{self._cfg.metadata.get('profile_id', 'SIM')}",
                "profile_id": self._cfg.metadata.get("profile_id", "SIM"),
                "bar_close_ts": ts_iso,
                "signal": signal_enum,
                "reason": reason,
                "passed_filters": passed_filters,
                "in_card_window": passed_filters, # Simplified for SilverAnalyzer
                "snapshot": {
                    "close": market_snapshot.get("close"),
                    "rsi": rsi_15m,
                    "volume_rel": volume_rel,
                    "atr_pct": atr_pct,
                }
            })

        if passed_filters:
            # Calculate confidence based on how many filters are defined
            confidence = 1.0
            
            signals.append(
                MarketSignal(
                    signal_id=str(uuid.uuid4()),
                    symbol=self._cfg.symbol,
                    timeframe=self._cfg.timeframe,
                    signal_type="SILVER_ENTRY",
                    direction="long",
                    confidence=confidence,
                    timestamp=datetime.now(),
                    metadata={
                        "source": "SilverAnalyzer",
                        "rsi_15m": rsi_15m,
                        "volume_rel": volume_rel,
                        "atr_pct": atr_pct,
                        "quality_score": quality_score,
                    },
                )
            )
        
        return signals


class SilverStrategist(IStrategist):
    """
    Silver Strategist - evaluates SILVER_ENTRY signals and creates trade decisions.
    
    For now:
    - If it sees a SILVER_ENTRY signal, it proposes a BUY decision
      with TP/SL from the config.
    - Risk per trade is configurable.
    """
    
    def __init__(self, cfg: SilverStrategyConfig, risk_per_trade_pct: float = 1.0) -> None:
        """
        Initialize SilverStrategist with strategy config.
        
        Args:
            cfg: SilverStrategyConfig loaded from strategy card.
            risk_per_trade_pct: Percentage of capital to risk per trade.
        """
        self._cfg = cfg
        self._requested_risk_pct = risk_per_trade_pct
        
        # Apply risk contract cap if present
        effective_risk = risk_per_trade_pct
        if cfg.max_risk_per_trade is not None:
            # Convert max_risk_per_trade (0.01) to percentage (1.0)
            max_risk_pct = cfg.max_risk_per_trade * 100.0
            effective_risk = min(risk_per_trade_pct, max_risk_pct)
        self._risk_pct = effective_risk
    
    def evaluate(self, signal: MarketSignal, account: AccountState) -> TradeDecision | None:
        """
        Evaluate a signal and create a trade decision if appropriate.
        
        Args:
            signal: The market signal to evaluate.
            account: Current account state.
            
        Returns:
            TradeDecision if signal is SILVER_ENTRY, None otherwise.
        """
        if signal.signal_type != "SILVER_ENTRY":
            return None
        
        # Create trade decision
        return TradeDecision(
            decision_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            symbol=self._cfg.symbol,
            timeframe=self._cfg.timeframe,
            action="open_long",
            entry_price=None,  # Will be filled by executor
            stop_loss=None,  # Will be calculated based on sl_pct
            take_profit=None,  # Will be calculated based on tp_pct
            position_size=account.capital * (self._risk_pct / 100.0),
            reason=f"SILVER_ENTRY_V1",
            metadata={
                "tp_pct": self._cfg.tp_pct,
                "sl_pct": self._cfg.sl_pct,
                "max_horizon_bars": self._cfg.max_horizon_bars,
                "signal_confidence": signal.confidence,
                "risk_per_trade_requested": self._requested_risk_pct,
                "risk_per_trade_effective": self._risk_pct,
                "risk_contract_max": self._cfg.max_risk_per_trade,
            },
        )
