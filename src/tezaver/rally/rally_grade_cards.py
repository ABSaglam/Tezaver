"""
Tezaver Rally Grade Cards
=========================

Computes Diamond / Gold / Silver / Bronze grade summaries
based on rally performance (future_max_gain_pct).
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd


GRADE_THRESHOLDS = {
    "Diamond": 0.30,  # 30%+
    "Gold": 0.20,     # 20%+
    "Silver": 0.10,   # 10%+
    "Bronze": 0.05,   # 5%+
}

MIN_SAMPLE_PER_GRADE = 3  # 3'ten az ise "yetersiz örnek" say


@dataclass
class GradeSummary:
    """Summary statistics for a specific grade (Diamond/Gold/Silver/Bronze)."""
    grade: str
    count: int
    min_gain_pct: float
    max_gain_pct: float
    avg_gain_pct: float
    avg_bars_to_peak: float
    rsi_p25: Optional[float]
    rsi_p75: Optional[float]
    vol_p25: Optional[float]
    vol_p75: Optional[float]
    atr_p25: Optional[float]
    atr_p75: Optional[float]
    quality_p25: Optional[float]
    quality_p75: Optional[float]
    has_enough_samples: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _quantile_safe(series: pd.Series, q: float) -> Optional[float]:
    """Safely compute quantile, returning None if series is empty."""
    series = series.dropna()
    if len(series) == 0:
        return None
    return float(series.quantile(q))


def _build_grade_summary(
    df: pd.DataFrame, 
    grade: str, 
    min_gain: float, 
    next_min_gain: Optional[float]
) -> GradeSummary:
    """
    Build summary for a grade:
      - min_gain <= gain < next_min_gain (or just min_gain+ if no upper bound)
    """
    gains = df["future_max_gain_pct"]

    if next_min_gain is None:
        mask = gains >= min_gain
    else:
        mask = (gains >= min_gain) & (gains < next_min_gain)

    gdf = df.loc[mask].copy()
    count = int(len(gdf))

    if count == 0:
        return GradeSummary(
            grade=grade,
            count=0,
            min_gain_pct=0.0,
            max_gain_pct=0.0,
            avg_gain_pct=0.0,
            avg_bars_to_peak=0.0,
            rsi_p25=None,
            rsi_p75=None,
            vol_p25=None,
            vol_p75=None,
            atr_p25=None,
            atr_p75=None,
            quality_p25=None,
            quality_p75=None,
            has_enough_samples=False,
        )

    gains_clean = gdf["future_max_gain_pct"].dropna()
    
    # Check for bars_to_peak column
    bars = gdf["bars_to_peak"].dropna() if "bars_to_peak" in gdf.columns else pd.Series(dtype=float)

    min_gain_pct = float(gains_clean.min()) * 100.0 if len(gains_clean) else 0.0
    max_gain_pct = float(gains_clean.max()) * 100.0 if len(gains_clean) else 0.0
    avg_gain_pct = float(gains_clean.mean()) * 100.0 if len(gains_clean) else 0.0
    avg_bars_to_peak = float(bars.mean()) if len(bars) else 0.0

    # BTC 15m metric columns
    rsi_col = "rsi_15m" if "rsi_15m" in gdf.columns else "rsi"
    vol_col = "volume_rel_15m" if "volume_rel_15m" in gdf.columns else "volume_rel"
    atr_col = "atr_pct_15m" if "atr_pct_15m" in gdf.columns else "atr_pct"

    rsi_p25 = _quantile_safe(gdf[rsi_col], 0.25) if rsi_col in gdf.columns else None
    rsi_p75 = _quantile_safe(gdf[rsi_col], 0.75) if rsi_col in gdf.columns else None

    vol_p25 = _quantile_safe(gdf[vol_col], 0.25) if vol_col in gdf.columns else None
    vol_p75 = _quantile_safe(gdf[vol_col], 0.75) if vol_col in gdf.columns else None

    atr_p25 = _quantile_safe(gdf[atr_col], 0.25) if atr_col in gdf.columns else None
    atr_p75 = _quantile_safe(gdf[atr_col], 0.75) if atr_col in gdf.columns else None

    quality_p25 = _quantile_safe(gdf["quality_score"], 0.25) if "quality_score" in gdf.columns else None
    quality_p75 = _quantile_safe(gdf["quality_score"], 0.75) if "quality_score" in gdf.columns else None

    has_enough = count >= MIN_SAMPLE_PER_GRADE

    return GradeSummary(
        grade=grade,
        count=count,
        min_gain_pct=min_gain_pct,
        max_gain_pct=max_gain_pct,
        avg_gain_pct=avg_gain_pct,
        avg_bars_to_peak=avg_bars_to_peak,
        rsi_p25=rsi_p25,
        rsi_p75=rsi_p75,
        vol_p25=vol_p25,
        vol_p75=vol_p75,
        atr_p25=atr_p25,
        atr_p75=atr_p75,
        quality_p25=quality_p25,
        quality_p75=quality_p75,
        has_enough_samples=has_enough,
    )


def compute_btc_15m_grade_summaries() -> Dict[str, GradeSummary]:
    """
    Compute grade summaries for BTCUSDT 15m:
    - Reads library/fast15_rallies/BTCUSDT/fast15_rallies.parquet
    - Returns Diamond/Gold/Silver/Bronze summaries
    """
    rallies_path = Path("library/fast15_rallies/BTCUSDT/fast15_rallies.parquet")
    if not rallies_path.exists():
        raise FileNotFoundError(
            f"BTCUSDT 15m rally dataset not found at {rallies_path}. "
            "Grade kartları için bu dosyanın üretilmiş olması gerekiyor."
        )

    df = pd.read_parquet(rallies_path)

    # Check required column
    if "future_max_gain_pct" not in df.columns:
        raise ValueError(
            "Dataset missing 'future_max_gain_pct' column. "
            "Grade kartları için bu alan gerekli."
        )

    # Sort thresholds descending for proper range assignment
    ordered = sorted(GRADE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True)
    summaries: Dict[str, GradeSummary] = {}

    for i, (grade, min_gain) in enumerate(ordered):
        # Previous (higher) threshold is the upper bound
        next_min_gain = None
        if i > 0:
            prev_grade, prev_min = ordered[i - 1]
            next_min_gain = prev_min

        summaries[grade] = _build_grade_summary(df, grade, min_gain, next_min_gain)

    return summaries


# =============================================================================
# SILVER GRADE STORY (v1)
# =============================================================================

def _safe_series_stats(s: pd.Series) -> Optional[Dict[str, float]]:
    """
    Compute basic stats (count, min, max, mean, p25, p50, p75).
    Returns None if empty or all NaN.
    """
    s = s.dropna()
    if s.empty:
        return None

    return {
        "count": int(s.shape[0]),
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "p25": float(s.quantile(0.25)),
        "p50": float(s.quantile(0.50)),
        "p75": float(s.quantile(0.75)),
    }


def _safe_value_counts(s: pd.Series) -> Dict[str, float]:
    """
    Normalized value_counts for categorical columns.
    """
    s = s.dropna().astype(str)
    if s.empty:
        return {}
    vc = s.value_counts(normalize=True)
    return {str(k): float(v) for k, v in vc.to_dict().items()}


def _load_btc_15m_rally_dataset() -> pd.DataFrame:
    """Load BTC 15m rally dataset."""
    rallies_path = Path("library/fast15_rallies/BTCUSDT/fast15_rallies.parquet")
    if not rallies_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(rallies_path)


def _load_rally_dataset(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load rally dataset for any supported timeframe.
    
    Paths:
      - 15m: library/fast15_rallies/{symbol}/fast15_rallies.parquet
      - 1h:  library/time_labs/1h/{symbol}/rallies_1h.parquet
      - 4h:  library/time_labs/4h/{symbol}/rallies_4h.parquet
    """
    if timeframe == "15m":
        path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    elif timeframe in ["1h", "4h"]:
        path = Path(f"library/time_labs/{timeframe}/{symbol}/rallies_{timeframe}.parquet")
    else:
        return pd.DataFrame()
    
    if not path.exists():
        return pd.DataFrame()
    
    return pd.read_parquet(path)


def _get_tf_column_names(timeframe: str) -> Dict[str, str]:
    """
    Get column name mapping for timeframe-specific columns.
    
    Returns dict with keys: rsi, rsi_ema, volume_rel, atr_pct
    """
    tf = timeframe
    return {
        "rsi": f"rsi_{tf}",
        "rsi_ema": f"rsi_ema_{tf}",
        "volume_rel": f"volume_rel_{tf}",
        "atr_pct": f"atr_pct_{tf}",
    }


def compute_btc_15m_silver_story_v1() -> Dict[str, Any]:
    """
    Compute 'story' card for BTCUSDT 15m Silver grade 
    (future_max_gain_pct ∈ [10%, 20%)).

    Static snapshot:
      - 15m RSI / Volume / ATR / Quality / Gain / Bars to peak
      - MACD phase, rally shape, 1h/4h/1d regime distributions

    Returns:
      Dict with has_enough_samples, static_snapshot_15m, mtf_snapshot, relations
    """
    import json as _json

    df = _load_btc_15m_rally_dataset()

    if df is None or df.empty:
        return {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "grade": "Silver",
            "has_enough_samples": False,
            "reason": "dataset_empty",
        }

    # Silver: 10% <= gain < 20%
    if "future_max_gain_pct" not in df.columns:
        return {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "grade": "Silver",
            "has_enough_samples": False,
            "reason": "missing_gain_column",
        }

    silver_mask = (df["future_max_gain_pct"] >= 0.10) & (df["future_max_gain_pct"] < 0.20)
    silver_df = df.loc[silver_mask].copy()

    sample_count = int(silver_df.shape[0])
    has_enough_samples = sample_count >= 3

    if not has_enough_samples:
        return {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "grade": "Silver",
            "sample_count": sample_count,
            "has_enough_samples": False,
            "reason": "not_enough_samples",
        }

    # --- Static snapshot (15m core) ---
    static_snapshot: Dict[str, Any] = {}
    
    core_cols = [
        "rsi_15m", "rsi_ema_15m", "volume_rel_15m", "atr_pct_15m",
        "quality_score", "future_max_gain_pct", "bars_to_peak",
        "pre_peak_drawdown_pct", "trend_efficiency"
    ]
    
    for col in core_cols:
        if col in silver_df.columns:
            static_snapshot[col] = _safe_series_stats(silver_df[col])
        else:
            static_snapshot[col] = None

    # RSI gap (rsi - rsi_ema)
    if "rsi_15m" in silver_df.columns and "rsi_ema_15m" in silver_df.columns:
        rsi_gap = silver_df["rsi_15m"] - silver_df["rsi_ema_15m"]
        static_snapshot["rsi_gap_15m"] = _safe_series_stats(rsi_gap)

    # --- Multi-timeframe snapshot ---
    mtf_snapshot: Dict[str, Any] = {}

    for tf in ["1h", "4h", "1d"]:
        tf_block: Dict[str, Any] = {}
        rsi_col = f"rsi_{tf}"
        rsi_ema_col = f"rsi_ema_{tf}"
        macd_phase_col = f"macd_phase_{tf}"
        regime_col = f"regime_{tf}"

        if rsi_col in silver_df.columns:
            tf_block["rsi"] = _safe_series_stats(silver_df[rsi_col])
        if rsi_ema_col in silver_df.columns:
            tf_block["rsi_ema"] = _safe_series_stats(silver_df[rsi_ema_col])
            if rsi_col in silver_df.columns:
                tf_block["rsi_gap"] = _safe_series_stats(
                    silver_df[rsi_col] - silver_df[rsi_ema_col]
                )
        if macd_phase_col in silver_df.columns:
            tf_block["macd_phase_dist"] = _safe_value_counts(silver_df[macd_phase_col])
        if regime_col in silver_df.columns:
            tf_block["regime_dist"] = _safe_value_counts(silver_df[regime_col])

        if tf_block:
            mtf_snapshot[tf] = tf_block

    # --- Relations ---
    relations: Dict[str, Any] = {}

    # RSI vs RSI-EMA (15m)
    if "rsi_15m" in silver_df.columns and "rsi_ema_15m" in silver_df.columns:
        rsi = silver_df["rsi_15m"]
        rsi_ema = silver_df["rsi_ema_15m"]
        valid = rsi.notna() & rsi_ema.notna()
        if valid.any():
            above = (rsi > rsi_ema) & valid
            below = (rsi < rsi_ema) & valid
            close_band = (rsi.sub(rsi_ema).abs() <= 2.0) & valid

            relations["rsi_vs_ema_15m"] = {
                "above_rate": float(above.mean()),
                "below_rate": float(below.mean()),
                "close_band_rate": float(close_band.mean()),
            }

    # Shape distribution
    if "rally_shape" in silver_df.columns:
        relations["shape_dist"] = _safe_value_counts(silver_df["rally_shape"])

    # MACD phase x shape (15m)
    if "macd_phase_15m" in silver_df.columns and "rally_shape" in silver_df.columns:
        combo = silver_df[["macd_phase_15m", "rally_shape"]].dropna().astype(str)
        if not combo.empty:
            grouped = combo.groupby(["macd_phase_15m", "rally_shape"]).size()
            total = float(grouped.sum())
            if total > 0:
                relations["macd_phase_15m_x_shape"] = {
                    f"{phase}__{shape}": float(count / total)
                    for (phase, shape), count in grouped.to_dict().items()
                }

    # Regime distribution for each TF
    for tf in ["1h", "4h", "1d"]:
        regime_col = f"regime_{tf}"
        if regime_col in silver_df.columns:
            relations[f"regime_{tf}_dist"] = _safe_value_counts(silver_df[regime_col])

    story: Dict[str, Any] = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "grade": "Silver",
        "sample_count": sample_count,
        "has_enough_samples": has_enough_samples,
        "static_snapshot_15m": static_snapshot,
        "mtf_snapshot": mtf_snapshot,
        "relations": relations,
    }

    return story


def save_btc_15m_silver_story_v1(path: Optional[Path] = None) -> Path:
    """Save Silver story output to JSON."""
    import json as _json
    
    if path is None:
        path = Path("data/coin_profiles/BTCUSDT/15m/grade_story_silver_v1.json")

    story = compute_btc_15m_silver_story_v1()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        _json.dump(story, f, ensure_ascii=False, indent=2)

    return path


def load_btc_15m_silver_story_v1(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load story from JSON. Returns None if file doesn't exist."""
    import json as _json
    
    if path is None:
        path = Path("data/coin_profiles/BTCUSDT/15m/grade_story_silver_v1.json")

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


# =============================================================================
# SILVER STRATEGY CARD (v1/v2-ML)
# =============================================================================

ML_ENTRY_INSIGHTS_PATH = Path("data/ai_insights/BTCUSDT/15m/entry_feature_insights_v1.json")
SL_RECOMMENDATION_PATH = Path("data/ai_insights/BTCUSDT/15m/silver_sl_recommendation_v1.json")


def _maybe_override_sl_from_recommendation(
    symbol: str,
    timeframe: str,
    base_sl_pct: float,
) -> tuple[float, str]:
    """
    Override SL with calibrated recommendation if available.
    
    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        base_sl_pct: Fallback SL from story calculation.
        
    Returns:
        Tuple of (final_sl_pct, source_string)
    """
    import json as _json
    
    insights_path = Path(f"data/ai_insights/{symbol}/{timeframe}/silver_sl_recommendation_v1.json")
    
    if not insights_path.exists():
        return base_sl_pct, "story_dd_p25"
    
    try:
        with insights_path.open("r", encoding="utf-8") as f:
            data = _json.load(f)
        rec = float(data.get("recommended_sl_pct", base_sl_pct))
        return rec, "sl_calibration_v1"
    except Exception:
        return base_sl_pct, "story_dd_p25"


def _load_entry_feature_insights_v1(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load BTC 15m entry feature insights from JSON."""
    import json as _json
    
    if path is None:
        path = ML_ENTRY_INSIGHTS_PATH

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


def _get_feature_insight(
    insights: Dict[str, Any],
    feature_name: str,
) -> Optional[Dict[str, Any]]:
    """Get single feature insight from the report."""
    feats = insights.get("features", [])
    for item in feats:
        if item.get("feature") == feature_name and item.get("available", False):
            return item
    return None


def _build_silver_ml_filters_from_insights(
    insights: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build ML-based filters from entry feature insights.
    
    Features used:
      - feat_rsi_gap_1d
      - feat_atr_pct_15m
      - feat_rsi_1h
    """
    ml_filters: Dict[str, Any] = {}

    # 1) 1D RSI Gap (RSI - EMA)
    item_gap = _get_feature_insight(insights, "feat_rsi_gap_1d")
    if item_gap is not None:
        g = item_gap.get("good_stats", {})
        g_p25 = g.get("p25")
        g_p75 = g.get("p75")
        if g_p25 is not None and g_p75 is not None:
            gap_min = float(g_p25)
            gap_max = float(g_p75)
            # Good entries prefer RSI below EMA
            if gap_max > 0.0:
                gap_max = 0.0
            ml_filters["rsi_gap_1d"] = {
                "feature": "feat_rsi_gap_1d",
                "min": gap_min,
                "max": gap_max,
                "intuition": "Girişte günlük RSI EMA'nın hafif altında; henüz tam toparlanmamış ortam.",
            }

    # 2) ATR % 15m
    item_atr = _get_feature_insight(insights, "feat_atr_pct_15m")
    if item_atr is not None:
        g = item_atr.get("good_stats", {})
        o = item_atr.get("other_stats", {})
        g_p25 = g.get("p25")
        g_p75 = g.get("p75")
        o_p75 = o.get("p75")

        if g_p25 is not None and g_p75 is not None and o_p75 is not None:
            # Volatility should be high
            atr_min = max(float(g_p25), float(o_p75))
            atr_max = float(g_p75)
            if atr_min < atr_max:
                ml_filters["atr_pct_15m"] = {
                    "feature": "feat_atr_pct_15m",
                    "min": atr_min,
                    "max": atr_max,
                    "intuition": "Girişte 15m ATR görece yüksek; sakin değil, hareket var.",
                }

    # 3) RSI 1H
    item_rsi1h = _get_feature_insight(insights, "feat_rsi_1h")
    if item_rsi1h is not None:
        g = item_rsi1h.get("good_stats", {})
        g_p25 = g.get("p25")
        g_p75 = g.get("p75")

        if g_p25 is not None and g_p75 is not None:
            # Keep oversold character
            rsi1h_min = max(0.0, float(g_p25))
            rsi1h_max = min(35.0, float(g_p75))
            if rsi1h_min < rsi1h_max:
                ml_filters["rsi_1h"] = {
                    "feature": "feat_rsi_1h",
                    "min": rsi1h_min,
                    "max": rsi1h_max,
                    "intuition": "Girişte 1h RSI görece düşük; coin hâlâ yıpranmış, dipten toparlanma evresi.",
                }

    return ml_filters


def build_btc_15m_silver_strategy_card_v1() -> Dict[str, Any]:
    """
    Build a data-driven strategy card from Silver Grade story.
    Now includes ML-based filters from entry feature insights (v2).

    Source: grade_story_silver_v1.json + entry_feature_insights_v1.json
    Output: Strategy card with filters and ML filters
    """
    import math
    
    story = load_btc_15m_silver_story_v1()
    if story is None or not story.get("has_enough_samples", False):
        return {
            "profile_id": "BTC15M_SILVER_STRATEGY_V1",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "ok": False,
            "reason": "story_missing_or_not_enough_samples",
            "source_story_path": "data/coin_profiles/BTCUSDT/15m/grade_story_silver_v1.json",
        }

    static_15m = story.get("static_snapshot_15m", {})
    relations = story.get("relations", {})

    rsi_stats = static_15m.get("rsi_15m") or {}
    vol_stats = static_15m.get("volume_rel_15m") or {}
    atr_stats = static_15m.get("atr_pct_15m") or {}
    q_stats = static_15m.get("quality_score") or {}
    gain_stats = static_15m.get("future_max_gain_pct") or {}
    bars_stats = static_15m.get("bars_to_peak") or {}
    dd_stats = static_15m.get("pre_peak_drawdown_pct") or {}

    shape_dist = relations.get("shape_dist", {})

    # ---- ENTRY FILTERS ----

    rsi_min = rsi_stats.get("p25")
    rsi_max = rsi_stats.get("p75")

    vol_min = vol_stats.get("p25")
    vol_max = vol_stats.get("p75")

    atr_min = atr_stats.get("p25")
    atr_max = atr_stats.get("p75")

    q_p25 = q_stats.get("p25")
    if q_p25 is not None:
        quality_min = max(float(q_p25), 60.0)
    else:
        quality_min = 60.0

    allowed_shapes = []
    for shape, rate in shape_dist.items():
        if rate >= 0.15:
            allowed_shapes.append(shape)
    if not allowed_shapes and shape_dist:
        allowed_shapes = list(shape_dist.keys())

    # ---- EXIT / RISK PARAMETERS ----

    tp_pct = 0.10
    if gain_stats:
        g_mean = float(gain_stats.get("mean", 0.12))
        tp_pct = max(0.07, min(0.18, g_mean * 0.8))

    # Base SL from story (dd_p25 * 1.2)
    base_sl_pct = 0.035
    if dd_stats:
        dd_p25 = dd_stats.get("p25")
        if dd_p25 is not None:
            base_sl_pct = min(0.05, abs(float(dd_p25)) * 1.2)

    # Override SL with calibration if available
    sl_pct, sl_source = _maybe_override_sl_from_recommendation("BTCUSDT", "15m", base_sl_pct)

    max_horizon_bars = 32
    if bars_stats:
        b_p75 = bars_stats.get("p75")
        if b_p75 is not None:
            max_horizon_bars = int(math.ceil(float(b_p75)))

    card: Dict[str, Any] = {
        "profile_id": "BTC15M_SILVER_STRATEGY_V1",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "ok": True,
        "source_story_path": "data/coin_profiles/BTCUSDT/15m/grade_story_silver_v1.json",
        "sample_count": story.get("sample_count", 0),
        "filters": {
            "rsi_15m": {
                "min": rsi_min,
                "max": rsi_max,
            },
            "volume_rel_15m": {
                "min": vol_min,
                "max": vol_max,
            },
            "atr_pct_15m": {
                "min": atr_min,
                "max": atr_max,
            },
            "quality_score": {
                "min": quality_min,
                "max": None,
            },
            "rally_shape": {
                "allowed": allowed_shapes,
                "shape_dist": shape_dist,
            },
        },
        "risk": {
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "base_sl_pct_from_story": base_sl_pct,
            "sl_source": sl_source,
            "max_horizon_bars": max_horizon_bars,
        },
        "notes": {
            "tp_rule": "tp_pct ~= future_max_gain_mean * 0.8, clamp [7%,18%]",
            "sl_rule": "sl_pct from sl_calibration_v1 or |pre_peak_drawdown_p25| * 1.2",
            "quality_rule": "quality_score >= max(Silver p25, 60)",
            "shapes_rule": "shape rate >= 15%",
        },
    }

    # --- ML-based filters (v2 behavior) ---
    insights = _load_entry_feature_insights_v1()
    if insights is not None:
        ml_filters = _build_silver_ml_filters_from_insights(insights)
        if ml_filters:
            card["ml_filters"] = ml_filters
            card["ml_insights_source_path"] = str(ML_ENTRY_INSIGHTS_PATH)
            card["version"] = "v2_ml"
        else:
            card["version"] = "v1"
    else:
        card["version"] = "v1"

    return card


def save_btc_15m_silver_strategy_card_v1(path: Optional[Path] = None) -> Path:
    """Save Silver Strategy Card v1 to JSON."""
    import json as _json
    
    if path is None:
        path = Path("data/coin_profiles/BTCUSDT/15m/silver_strategy_card_v1.json")

    card = build_btc_15m_silver_strategy_card_v1()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        _json.dump(card, f, ensure_ascii=False, indent=2)

    return path


def load_btc_15m_silver_strategy_card_v1(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load Strategy Card from JSON. Returns None if file doesn't exist."""
    import json as _json
    
    if path is None:
        path = Path("data/coin_profiles/BTCUSDT/15m/silver_strategy_card_v1.json")

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


# =============================================================================
# GENERIC MULTI-TIMEFRAME SILVER STORY / STRATEGY CARD
# =============================================================================

def compute_silver_story_v1(symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Generic Silver Story for any supported timeframe (15m, 1h, 4h).
    
    Silver = 10% <= future_max_gain_pct < 20%
    """
    df = _load_rally_dataset(symbol, timeframe)
    
    if df is None or df.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "grade": "Silver",
            "has_enough_samples": False,
            "reason": "dataset_empty",
        }
    
    if "future_max_gain_pct" not in df.columns:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "grade": "Silver",
            "has_enough_samples": False,
            "reason": "missing_gain_column",
        }
    
    # Silver filter
    silver_mask = (df["future_max_gain_pct"] >= 0.10) & (df["future_max_gain_pct"] < 0.20)
    silver_df = df.loc[silver_mask].copy()
    
    sample_count = int(silver_df.shape[0])
    has_enough_samples = sample_count >= 3
    
    if not has_enough_samples:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "grade": "Silver",
            "sample_count": sample_count,
            "has_enough_samples": False,
            "reason": "not_enough_samples",
        }
    
    # Get TF-specific column names
    cols = _get_tf_column_names(timeframe)
    
    # Build static snapshot
    static_snapshot: Dict[str, Any] = {}
    
    core_cols = [
        cols["rsi"], cols["volume_rel"], cols["atr_pct"],
        "future_max_gain_pct", "bars_to_peak",
    ]
    
    for col in core_cols:
        if col in silver_df.columns:
            stats = _safe_series_stats(silver_df[col])
            if stats:
                static_snapshot[col] = stats
    
    # Multi-TF RSI snapshot (if available)
    mtf_snapshot: Dict[str, Any] = {}
    for mtf in ["rsi_15m", "rsi_1h", "rsi_4h", "rsi_1d"]:
        if mtf in silver_df.columns:
            stats = _safe_series_stats(silver_df[mtf])
            if stats:
                mtf_snapshot[mtf] = stats
    
    # Shape distribution (if available)
    shape_dist = {}
    if "rally_shape" in silver_df.columns:
        shape_dist = _safe_value_counts(silver_df["rally_shape"])
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "grade": "Silver",
        "sample_count": sample_count,
        "has_enough_samples": True,
        f"static_snapshot_{timeframe}": static_snapshot,
        "mtf_snapshot": mtf_snapshot,
        "relations": {
            "shape_dist": shape_dist,
        },
    }


def build_silver_strategy_card_v1(symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Build Silver Strategy Card for any timeframe.
    Uses story stats to derive entry filters and TP/SL/Horizon.
    """
    import math
    
    story = compute_silver_story_v1(symbol, timeframe)
    
    if not story.get("has_enough_samples", False):
        return {
            "profile_id": f"BTC{timeframe.upper()}_SILVER_STRATEGY_V1",
            "symbol": symbol,
            "timeframe": timeframe,
            "ok": False,
            "reason": story.get("reason", "story_not_ready"),
        }
    
    cols = _get_tf_column_names(timeframe)
    static_key = f"static_snapshot_{timeframe}"
    static = story.get(static_key, {})
    
    # Extract stats
    rsi_stats = static.get(cols["rsi"]) or {}
    vol_stats = static.get(cols["volume_rel"]) or {}
    atr_stats = static.get(cols["atr_pct"]) or {}
    gain_stats = static.get("future_max_gain_pct") or {}
    bars_stats = static.get("bars_to_peak") or {}
    
    shape_dist = story.get("relations", {}).get("shape_dist", {})
    
    # Entry filters
    rsi_min = rsi_stats.get("p25")
    rsi_max = rsi_stats.get("p75")
    vol_min = vol_stats.get("p25")
    vol_max = vol_stats.get("p75")
    atr_min = atr_stats.get("p25")
    atr_max = atr_stats.get("p75")
    
    # Shapes with >= 15% rate
    allowed_shapes = []
    for shape, rate in shape_dist.items():
        if rate >= 0.15:
            allowed_shapes.append(shape)
    if not allowed_shapes and shape_dist:
        allowed_shapes = list(shape_dist.keys())
    
    # TP: mean * 0.8, clamp [7%, 18%]
    tp_pct = 0.10
    if gain_stats:
        g_mean = float(gain_stats.get("mean", 0.12))
        tp_pct = max(0.07, min(0.18, g_mean * 0.8))
    
    # SL: 3.5% default (no drawdown data for 1h/4h yet)
    sl_pct = 0.035
    
    # Horizon: bars_to_peak p75
    max_horizon_bars = 24
    if bars_stats:
        b_p75 = bars_stats.get("p75")
        if b_p75 is not None:
            max_horizon_bars = int(math.ceil(float(b_p75)))
    
    card = {
        "profile_id": f"BTC{timeframe.upper()}_SILVER_STRATEGY_V1",
        "symbol": symbol,
        "timeframe": timeframe,
        "ok": True,
        "sample_count": story.get("sample_count", 0),
        "filters": {
            cols["rsi"]: {"min": rsi_min, "max": rsi_max},
            cols["volume_rel"]: {"min": vol_min, "max": vol_max},
            cols["atr_pct"]: {"min": atr_min, "max": atr_max},
            "rally_shape": {"allowed": allowed_shapes, "shape_dist": shape_dist},
        },
        "risk": {
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "max_horizon_bars": max_horizon_bars,
        },
        "version": "v1",
    }
    
    return card


def save_silver_strategy_card_v1(symbol: str, timeframe: str) -> Path:
    """Save generic Silver Strategy Card to JSON."""
    import json as _json
    
    card = build_silver_strategy_card_v1(symbol, timeframe)
    path = Path(f"data/coin_profiles/{symbol}/{timeframe}/silver_strategy_card_v1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with path.open("w", encoding="utf-8") as f:
        _json.dump(card, f, ensure_ascii=False, indent=2)
    
    return path


def load_silver_strategy_card_v1(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    """Load generic Silver Strategy Card from JSON."""
    import json as _json
    
    path = Path(f"data/coin_profiles/{symbol}/{timeframe}/silver_strategy_card_v1.json")
    if not path.exists():
        return None
    
    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


if __name__ == "__main__":
    # CLI: Generate Silver story and strategy cards for all timeframes
    print("Generating BTC Silver cards for 15m, 1h, 4h...")
    
    for tf in ["15m", "1h", "4h"]:
        card = build_silver_strategy_card_v1("BTCUSDT", tf)
        if card.get("ok"):
            path = save_silver_strategy_card_v1("BTCUSDT", tf)
            print(f"  {tf}: Silver strategy card saved ({card['sample_count']} samples)")
        else:
            print(f"  {tf}: Not enough samples or data missing")
    
    # Also generate 15m specific files for backward compatibility
    story_path = save_btc_15m_silver_story_v1()
    print(f"\nSilver story v1 (15m) saved to: {story_path}")
    
    strategy_path = save_btc_15m_silver_strategy_card_v1()
    print(f"Silver strategy card v1 (15m) saved to: {strategy_path}")

