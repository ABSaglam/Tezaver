"""
Tezaver Sim v1.1 - Simulation Preset System
===========================================

Defines standard simulation presets for rapid backtesting.
Each preset maps to a specific RallySimConfig.
"""

from dataclasses import dataclass, replace
from typing import List, Dict, Optional, Any

from tezaver.sim.sim_config import RallySimConfig

@dataclass(frozen=True)
class SimPreset:
    """
    A stable, versioned simulation strategy preset.
    """
    id: str                 # Unique ID, e.g. "FAST15_SCALPER_V1"
    label_tr: str           # User-facing label (Turkish)
    description_tr: str     # Description for UI tooltip/markdown
    timeframe: str          # "15m", "1h", "4h"
    base_config: RallySimConfig
    tags: List[str]
    version: str            # Semver-like string

# --- Preset Definitions ---

_FAST15_SCALPER_V1 = SimPreset(
    id="FAST15_SCALPER_V1",
    label_tr="⚡ Fast15 – Hızlı Scalper v1",
    description_tr=(
        "**Yüksek Kalite Scalp:** Sadece yüksek puanlı ve temiz şekilli 15 dakikalık hızlı yükselişleri hedefler. "
        "Arka planda 4 saatlik Trend Soul desteği arar. Kısa vadeli (3-4 saat) tutma süresi vardır."
    ),
    timeframe="15m",
    version="1.1.0",
    tags=["scalp", "high_quality", "fast"],
    base_config=RallySimConfig(
        symbol="UNK", # Placeholder
        timeframe="15m",
        min_quality_score=70.0,
        allowed_shapes=["clean", "spike"],
        min_future_max_gain_pct=None,
        require_trend_soul_4h_gt=60.0,
        require_rsi_1d_gt=45.0, # Range 45-75 implies min 45. Max not supported by config yet? User prompt said "range". Config has "gt". We use min.
        tp_pct=0.07,  # ~7%
        sl_pct=0.035, # ~3.5%
        max_horizon_bars=14, # ~3.5 hours
        risk_per_trade_pct=0.01
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
        max_horizon_bars=60, # ~10 days (60 * 4h = 240h = 10 days)
        risk_per_trade_pct=0.005 # 0.5% risk
    )
)

_PRESETS: Dict[str, SimPreset] = {
    p.id: p for p in [
        _FAST15_SCALPER_V1,
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
    
    Args:
        preset: The source preset.
        symbol: The symbol to apply this config to.
        
    Returns:
        A new RallySimConfig instance with preset values.
    """
    # Create a copy using replace, updating the symbol
    return replace(preset.base_config, symbol=symbol)
