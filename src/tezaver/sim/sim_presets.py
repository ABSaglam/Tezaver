"""
Tezaver Sim v2 - Simulation Preset System
==========================================

Defines standard simulation presets for rapid backtesting.
Each preset maps to a specific RallySimConfig.
"""

from dataclasses import dataclass, replace
from typing import List, Dict, Optional

from tezaver.sim.sim_config import RallySimConfig


@dataclass(frozen=True)
class SimPreset:
    """
    A stable, versioned simulation strategy preset.
    """
    id: str                 # Unique ID
    label_tr: str           # User-facing label (Turkish)
    description_tr: str     # Description for UI tooltip/markdown
    timeframe: str          # "15m", "1h", "4h"
    base_config: RallySimConfig
    tags: List[str]
    version: str            # Semver-like string


# --- Preset Definitions ---

_BTC15M_STRATEGY_V1 = SimPreset(
    id="BTC15M_STRATEGY_V1",
    label_tr="⚡ BTC 15m – Çekirdek Strateji v1",
    description_tr=(
        "**BTC 15 Dakika Çekirdek:** BTCUSDT 15 dakikalık rally'ler için "
        "orta kaliteli event'leri hedefler. Basit ve sade bir başlangıç noktası."
    ),
    timeframe="15m",
    version="1.0.0",
    tags=["btc", "15m", "core"],
    base_config=RallySimConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        min_quality_score=60.0,            # Orta-üst kalite
        allowed_shapes=["clean", "choppy", "spike"],  # weak hariç
        min_future_max_gain_pct=None,
        require_trend_soul_4h_gt=None,     # Trend filtresi kapalı
        require_rsi_1d_gt=None,            # RSI filtresi kapalı
        tp_pct=0.07,                       # %7 take profit
        sl_pct=0.035,                      # %3.5 stop loss
        max_horizon_bars=24,               # 6 saat horizon (15m * 24)
        risk_per_trade_pct=0.01            # %1 risk per trade
    )
)

_H1_SWING_V1 = SimPreset(
    id="H1_SWING_V1",
    label_tr="🌊 H1 – Swing Trade v1",
    description_tr=(
        "**Orta Vade Swing:** 1 saatlik temiz ve dalgalı (choppy) yapıları değerlendirir. "
        "Daha geniş RSI aralığına ve tutma süresine (2-3 gün) sahiptir."
    ),
    timeframe="1h",
    version="1.1.0",
    tags=["swing", "medium_term"],
    base_config=RallySimConfig(
        symbol="UNK",
        timeframe="1h",
        min_quality_score=65.0,
        allowed_shapes=["clean", "choppy"],
        min_future_max_gain_pct=None,
        require_trend_soul_4h_gt=55.0,
        require_rsi_1d_gt=40.0,
        tp_pct=0.12,  # ~12%
        sl_pct=0.06,  # ~6%
        max_horizon_bars=50, # ~2 days
        risk_per_trade_pct=0.005 # 0.5% risk
    )
)

_H4_TREND_V1 = SimPreset(
    id="H4_TREND_V1",
    label_tr="🐘 H4 – Trend Follower v1",
    description_tr=(
        "**Uzun Vade Trend:** 4 saatlik güçlü trend sinyallerini takip eder. "
        "Yüksek Trend Soul ve RSI onayı gerektirir. Hedefleri geniştir."
    ),
    timeframe="4h",
    version="1.1.0",
    tags=["trend", "long_term"],
    base_config=RallySimConfig(
        symbol="UNK",
        timeframe="4h",
        min_quality_score=60.0,
        allowed_shapes=["clean", "choppy"],
        min_future_max_gain_pct=None,
        require_trend_soul_4h_gt=65.0,
        require_rsi_1d_gt=45.0,
        tp_pct=0.20,  # ~20%
        sl_pct=0.08,  # ~8%
        max_horizon_bars=60, # ~10 days
        risk_per_trade_pct=0.005 # 0.5% risk
    )
)

_PRESETS: Dict[str, SimPreset] = {
    p.id: p for p in [
        _BTC15M_STRATEGY_V1,
        _H1_SWING_V1,
        _H4_TREND_V1
    ]
}


# --- Public API ---

def get_all_presets() -> List[SimPreset]:
    """Return list of all registered simulation presets."""
    return list(_PRESETS.values())


def get_preset_by_id(preset_id: str) -> Optional[SimPreset]:
    """Retrieve a preset by its unique ID."""
    return _PRESETS.get(preset_id)


def build_config_from_preset(preset: SimPreset, symbol: str) -> RallySimConfig:
    """
    Create a fresh RallySimConfig from a preset.
    """
    return replace(preset.base_config, symbol=symbol)
