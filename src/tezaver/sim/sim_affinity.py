"""
Tezaver Sim v1.3 - Strategy Affinity Export
===========================================

Calculates strategy affinity scores (0-100) for simulation results
and exports profiles for decision making.
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime, timezone

from tezaver.sim.sim_scoreboard import PresetScore
from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import get_coin_profile_dir

logger = get_logger(__name__)

@dataclass
class AffinityConfig:
    min_trades_for_reliability: int = 15
    win_min: float = 0.30
    win_max: float = 0.80
    exp_min: float = -0.01   # -1% per trade
    exp_max: float = 0.02    # +2% per trade
    dd_min: float = -0.60    # -60%
    dd_max: float = -0.10    # -10%
    trades_ref: int = 20     # Reference point for full trade count score

@dataclass
class PresetAffinity:
    preset_id: str
    timeframe: str
    num_trades: int
    win_rate: float
    net_pnl_pct: float
    expectancy_pct: float
    max_drawdown_pct: float
    affinity_score: float
    affinity_grade: str
    status: str  # "reliable" | "low_data" | "bad"

@dataclass
class StrategyAffinitySummary:
    symbol: str
    base_equity: float
    presets: Dict[str, PresetAffinity]
    best_overall: Optional[PresetAffinity]
    summary_tr: Optional[str] = None
    generated_at: str = ""

def clamp(val, low, high):
    return max(low, min(val, high))

def normalize(val, low, high):
    """Normalize value to 0-1 range based on bounds."""
    if high == low: return 0.0
    return clamp((val - low) / (high - low), 0.0, 1.0)

def compute_preset_affinity(stats: PresetScore, cfg: AffinityConfig) -> PresetAffinity:
    """
    Calculate affinity score (0-100) and grade for a single preset result.
    """
    # 1. Normalize Components (Weighting heuristic)
    
    # Win Rate (0.3 - 0.8 range maps to 0-1)
    s_win = normalize(stats.win_rate, cfg.win_min, cfg.win_max)
    
    # Expectancy ( -1% to +2% range)
    # Note: expectancy_pct is usually passed as percentage (e.g. 1.5 for 1.5%)
    # If stats.expectancy_pct is e.g. 1.2, and cfg.exp_max is 0.02 (2%), we need to align units.
    # In dashboard we saw expectancy_pct formatted as %.2f.
    # Check PresetScore definition: expectancy_pct: float. 
    # Usually we convert R to %. Let's assume stats.expectancy_pct is e.g. 0.5 (for 0.5%).
    # Config exp_max = 0.02 seems to imply 2% if raw ratio, or 0.02%? 
    # Let's assume Config is in DECIMAL (0.02 = 2%) but stats might be PERCENT (2.0).
    # Let's standardize: Use decimal everywhere logic inside here.
    # If stats.expectancy_pct > 1.0 (e.g. 50), it is likely %. If < 0.1 likely decimal.
    # Actually sim_engine summarizes it as "expectancy_R" (decimal).
    # sim_scoreboard converts it: `expectancy_pct=float(results['expectancy_R']) * 100` -> So it is PERCENT.
    # So 1.5 = 1.5%.
    # Config: exp_max = 0.02. If that means 2%, then it is DECIMAL.
    # So we should compare `stats.expectancy_pct / 100` vs `cfg.exp_max`.
    
    exp_decimal = stats.expectancy_pct / 100.0
    s_exp = normalize(exp_decimal, cfg.exp_min, cfg.exp_max)
    
    # Drawdown (-60% to -10%). Less negative is better.
    # dd is negative (e.g. -0.2).
    # We want -0.1 to be score 1, -0.6 to be score 0.
    # normalize(-0.2, -0.6, -0.1) -> (-0.2 - (-0.6)) / (-0.1 - (-0.6)) = 0.4 / 0.5 = 0.8. Correct.
    s_dd = normalize(stats.max_drawdown_pct, cfg.dd_min, cfg.dd_max)
    
    # Trade Count Confidence
    # If trades < min, penalty. If trades > ref, full score.
    s_count = normalize(stats.num_trades, 0, cfg.trades_ref)
    
    # Weighted Score
    # Win: 25%, Exp: 40%, DD: 20%, Count: 15%
    raw_score = (s_win * 25) + (s_exp * 40) + (s_dd * 20) + (s_count * 15)
    
    # Penalties for low data or negative expectancy
    if stats.num_trades < 5:
        raw_score *= 0.5 # Severe penalty for very low data
        
    if exp_decimal < 0:
        raw_score *= 0.5 # Penalty for losing strategy
        
    final_score = clamp(raw_score, 0, 100)
    
    # Status & Grade
    if stats.num_trades >= cfg.min_trades_for_reliability:
        status = "reliable"
        if final_score >= 80: grade = "A+"
        elif final_score >= 70: grade = "A"
        elif final_score >= 60: grade = "B"
        elif final_score >= 40: grade = "C"
        else: grade = "D"
    elif stats.num_trades > 0:
        status = "low_data"
        grade = "N/A" # or tentative grade
        if final_score >= 60: grade = "B? (Low Data)"
        else: grade = "C? (Low Data)"
    else:
        status = "no_data"
        grade = "-"
        final_score = 0.0

    return PresetAffinity(
        preset_id=stats.preset_id,
        timeframe=stats.timeframe,
        num_trades=stats.num_trades,
        win_rate=stats.win_rate,
        net_pnl_pct=stats.net_pnl_pct,
        expectancy_pct=stats.expectancy_pct,
        max_drawdown_pct=stats.max_drawdown_pct,
        affinity_score=round(final_score, 1),
        affinity_grade=grade,
        status=status
    )

def select_best_overall(presets: Dict[str, PresetAffinity], cfg: AffinityConfig) -> Optional[PresetAffinity]:
    """
    Select the best strategy based on affinity score and reliability.
    """
    if not presets:
        return None
        
    # Filter reliable ones
    reliable = [p for p in presets.values() if p.status == "reliable"]
    
    if reliable:
        # Pick max score
        return max(reliable, key=lambda p: p.affinity_score)
    else:
        # Fallback to low_data if any have positive score
        low_data = [p for p in presets.values() if p.status == "low_data" and p.affinity_score > 40]
        if low_data:
            return max(low_data, key=lambda p: p.affinity_score)
            
    return None

def build_strategy_affinity_summary_tr(summary: StrategyAffinitySummary) -> Optional[str]:
    """Generate Turkish summary."""
    if not summary.best_overall:
        return "Bu coin için şu anda güvenilir bir strateji eşleşmesi bulunamadı. Yeterli sinyal verisi oluşmamış olabilir."
        
    best = summary.best_overall
    base_msg = (
        f"Simülasyon sonuçlarına göre, **{best.preset_id}** stratejisi bu coin ile "
        f"en yüksek uyumu (**Skor: {best.affinity_score}**) gösteriyor. "
        f"{best.num_trades} işlemde **%{best.win_rate*100:.1f}** başarı oranı "
        f"ve toplam **%{best.net_pnl_pct*100:.1f}** getiri sağladı."
    )
    
    if best.status == "low_data":
        base_msg += " (Not: İşlem sayısı az olduğu için sonuçlar kesinlik taşımaz.)"
        
    return base_msg

def compute_strategy_affinity(
    preset_scores: List[PresetScore],
    symbol: str,
    cfg: Optional[AffinityConfig] = None,
) -> StrategyAffinitySummary:
    """
    Aggregate preset scores into a full affinity summary.
    """
    if cfg is None:
        cfg = AffinityConfig()
        
    affinity_map = {}
    for score in preset_scores:
        aff = compute_preset_affinity(score, cfg)
        affinity_map[score.preset_id] = aff
        
    best = select_best_overall(affinity_map, cfg)
    
    summary = StrategyAffinitySummary(
        symbol=symbol,
        base_equity=10000.0, # Default assumption or could pass in
        presets=affinity_map,
        best_overall=best,
        generated_at=datetime.now(timezone.utc).isoformat()
    )
    
    summary.summary_tr = build_strategy_affinity_summary_tr(summary)
    
    return summary

def save_strategy_affinity(
    symbol: str,
    summary: StrategyAffinitySummary,
    sim_version: str = "1.3",
) -> Path:
    """Save affinity summary to JSON file."""
    profile_dir = get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = profile_dir / "sim_affinity.json"
    
    # Convert to JSON-compatible dict
    data = asdict(summary)
    data['meta'] = {"sim_version": sim_version, "config": "default"}
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Saved affinity profile for {symbol} to {out_path}")
    return out_path
