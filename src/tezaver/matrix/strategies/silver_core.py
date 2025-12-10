# Matrix V2 Silver Core Strategy
"""
Silver strategy configuration, analyzer, and strategist for Matrix v2.

This module provides the adapter layer between Coin Lab's Silver strategy cards
and Matrix's trading engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import uuid

from tezaver.matrix.core.engine import IAnalyzer, IStrategist
from tezaver.matrix.core.types import MarketSignal, TradeDecision
from tezaver.matrix.core.account import AccountState


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
    ml = raw.get("ml_filters", {})
    exit_cfg = raw.get("exit", {})
    
    def _to_range(d: dict | None) -> tuple[float, float] | None:
        if not d:
            return None
        if "min" not in d or "max" not in d:
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
    
    def __init__(self, cfg: SilverStrategyConfig) -> None:
        """
        Initialize SilverAnalyzer with strategy config.
        
        Args:
            cfg: SilverStrategyConfig loaded from strategy card.
        """
        self._cfg = cfg
    
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
        
        # All filters must pass for signal
        if all([rsi_ok, volume_ok, atr_ok, quality_ok, ml_rsi_gap_ok, ml_atr_ok, ml_rsi_1h_ok]):
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
