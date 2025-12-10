# Silver Stop-Loss Calibration Module
"""
Calibrates stop-loss (SL) values for Silver strategy based on pre-peak drawdown distribution.

Produces:
- silver_drawdown_stats_v1.json: Drawdown distribution statistics
- silver_sl_recommendation_v1.json: Recommended SL based on p90 quantile
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]  # ml/ → tezaver/ → src/ → project root
DATASET_PATH = BASE_DIR / "data" / "ai_datasets" / "BTCUSDT" / "15m" / "rally_patterns_v1.parquet"
INSIGHTS_DIR = BASE_DIR / "data" / "ai_insights" / "BTCUSDT" / "15m"


@dataclass
class SilverDrawdownStats:
    """Statistics for Silver pattern pre-peak drawdown distribution."""
    symbol: str
    timeframe: str
    sample_count: int
    mean: float
    min: float
    max: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    source_column: str


@dataclass
class SilverSlRecommendation:
    """Recommended stop-loss based on drawdown analysis."""
    symbol: str
    timeframe: str
    recommended_sl_pct: float
    base_on_quantile: str
    quantile_value: float
    safety_factor: float
    note: str


def _load_btc_15m_patterns() -> pd.DataFrame:
    """Load BTC 15m rally patterns dataset."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Pattern dataset not found at {DATASET_PATH}")
    return pd.read_parquet(DATASET_PATH)


def _select_silver_subset(df: pd.DataFrame) -> Tuple[pd.Series, str]:
    """
    Select Silver / good entry subset and find drawdown column.
    
    Returns:
        Tuple of (drawdown series, column name used)
    """
    # Try different column names for Silver selection
    if "label_is_good_entry_v1" in df.columns:
        mask = df["label_is_good_entry_v1"] == True  # noqa: E712
    elif "label_is_silver" in df.columns:
        mask = df["label_is_silver"] == True  # noqa: E712
    elif "is_good_entry_v1" in df.columns:
        mask = df["is_good_entry_v1"] == True  # noqa: E712
    elif "is_silver" in df.columns:
        mask = df["is_silver"] == True  # noqa: E712
    else:
        # No filter - use all rows
        mask = pd.Series([True] * len(df), index=df.index)

    subset = df.loc[mask]

    # Drawdown column priority: feat_pre_peak_drawdown_pct > future_min_drawdown_pct
    if "feat_pre_peak_drawdown_pct" in subset.columns:
        col = "feat_pre_peak_drawdown_pct"
    elif "future_min_drawdown_pct" in subset.columns:
        col = "future_min_drawdown_pct"
    elif "label_future_min_drawdown_pct" in subset.columns:
        col = "label_future_min_drawdown_pct"
    else:
        raise ValueError("No drawdown column found (feat_pre_peak_drawdown_pct / future_min_drawdown_pct).")

    series = subset[col].dropna().astype(float)
    return series, col


def analyze_btc_15m_silver_drawdown_distribution() -> SilverDrawdownStats:
    """
    Analyze pre-peak drawdown distribution for Silver patterns.
    
    Returns:
        SilverDrawdownStats with percentile breakdown.
        
    Side effects:
        Writes silver_drawdown_stats_v1.json to insights directory.
    """
    df = _load_btc_15m_patterns()
    series, col = _select_silver_subset(df)

    if series.empty:
        raise ValueError("No silver / good entry rows found in pattern dataset.")

    q = np.percentile(series.values, [10, 25, 50, 75, 90, 95])

    stats = SilverDrawdownStats(
        symbol="BTCUSDT",
        timeframe="15m",
        sample_count=int(series.shape[0]),
        mean=float(series.mean()),
        min=float(series.min()),
        max=float(series.max()),
        p10=float(q[0]),
        p25=float(q[1]),
        p50=float(q[2]),
        p75=float(q[3]),
        p90=float(q[4]),
        p95=float(q[5]),
        source_column=col,
    )

    # Ensure output directory exists
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    
    out_path = INSIGHTS_DIR / "silver_drawdown_stats_v1.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(stats), f, indent=2, ensure_ascii=False)

    return stats


def build_btc_15m_silver_sl_recommendation(stats: SilverDrawdownStats) -> SilverSlRecommendation:
    """
    Build SL recommendation based on p90 drawdown.
    
    Logic:
      - Take abs(p90 drawdown)
      - Apply 1.1x safety factor
      - Clamp to [0.2%, 3%] range
    
    Args:
        stats: SilverDrawdownStats from distribution analysis.
        
    Returns:
        SilverSlRecommendation with calibrated SL.
        
    Side effects:
        Writes silver_sl_recommendation_v1.json to insights directory.
    """
    p90_abs = abs(stats.p90)
    safety_factor = 1.1
    raw_sl = p90_abs * safety_factor

    # Clamp to reasonable range
    lower = 0.002   # 0.2%
    upper = 0.03    # 3%
    recommended = min(max(raw_sl, lower), upper)

    rec = SilverSlRecommendation(
        symbol=stats.symbol,
        timeframe=stats.timeframe,
        recommended_sl_pct=float(round(recommended, 4)),
        base_on_quantile="p90",
        quantile_value=float(stats.p90),
        safety_factor=safety_factor,
        note="SL derived from p90(pre_peak_drawdown) * safety_factor, clamped to [0.2%, 3%].",
    )

    out_path = INSIGHTS_DIR / "silver_sl_recommendation_v1.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(rec), f, indent=2, ensure_ascii=False)

    return rec


def run_btc_15m_silver_sl_calibration() -> Dict[str, Any]:
    """
    Run full SL calibration pipeline for BTC Silver 15m.
    
    Returns:
        Dict with stats and recommendation.
    """
    stats = analyze_btc_15m_silver_drawdown_distribution()
    rec = build_btc_15m_silver_sl_recommendation(stats)

    print("=== BTC Silver 15m – SL Calibration ===")
    print()
    print(f"Samples        : {stats.sample_count}")
    print(f"Source Column  : {stats.source_column}")
    print()
    print("Drawdown Distribution:")
    print(f"  Mean         : {stats.mean:.4%}")
    print(f"  Min          : {stats.min:.4%}")
    print(f"  Max          : {stats.max:.4%}")
    print(f"  p10          : {stats.p10:.4%}")
    print(f"  p25          : {stats.p25:.4%}")
    print(f"  p50 (median) : {stats.p50:.4%}")
    print(f"  p75          : {stats.p75:.4%}")
    print(f"  p90          : {stats.p90:.4%}")
    print(f"  p95          : {stats.p95:.4%}")
    print()
    print("SL Recommendation:")
    print(f"  Based on     : {rec.base_on_quantile} = {rec.quantile_value:.4%}")
    print(f"  Safety Factor: {rec.safety_factor}x")
    print(f"  Recommended  : {rec.recommended_sl_pct:.4%}")
    print()
    print(f"Outputs saved to: {INSIGHTS_DIR}/")

    return {
        "stats": asdict(stats),
        "recommendation": asdict(rec),
    }


def load_sl_recommendation(symbol: str = "BTCUSDT", timeframe: str = "15m") -> float | None:
    """
    Load SL recommendation from insights file.
    
    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        
    Returns:
        Recommended SL percentage, or None if not found.
    """
    insights_path = (
        BASE_DIR
        / "data"
        / "ai_insights"
        / symbol
        / timeframe
        / "silver_sl_recommendation_v1.json"
    )
    
    if not insights_path.exists():
        return None
    
    try:
        with insights_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return float(data.get("recommended_sl_pct", 0.02))
    except Exception:
        return None


if __name__ == "__main__":
    run_btc_15m_silver_sl_calibration()
