"""
Tezaver Sim v1.5 - Strategy Promotion & Guardrails
==================================================

Implements the promotion rules (APPROVED, CANDIDATE, REJECTED) for simulation presets
based on affinity scores and performance metrics.
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Literal, List
from pathlib import Path
from datetime import datetime, timezone

from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import get_coin_profile_dir

logger = get_logger(__name__)

PromotionStatus = Literal["APPROVED", "CANDIDATE", "REJECTED"]

@dataclass
class StrategyPromotionConfig:
    """Configuration for strategy promotion thresholds."""
    min_trades_strong: int = 40
    min_trades_weak: int = 15
    min_score_candidate: float = 55.0
    min_score_approved: float = 70.0
    min_win_rate_approved: float = 0.52
    max_dd_approved: float = -0.30     # e.g -30%
    max_dd_candidate: float = -0.35    # e.g -35%
    min_expectancy_approved: float = 0.0

@dataclass
class StrategyPromotionDecision:
    """Decision details for a single preset."""
    preset_id: str
    affinity_score: float
    grade: str
    trade_count: int
    win_rate: float
    net_pnl_pct: float
    max_drawdown_pct: float
    expectancy_pct: float
    reliability: str  # "reliable" or "low_data"
    status: PromotionStatus

@dataclass
class StrategyPromotionSummary:
    """Summary of promotion decisions for a symbol."""
    symbol: str
    rules_version: str
    strategies: Dict[str, StrategyPromotionDecision]
    generated_at: str

def compute_promotion_for_preset(
    preset_id: str,
    affinity_score: float,
    grade: str,
    trade_count: int,
    win_rate: float,
    net_pnl_pct: float,
    max_drawdown_pct: float,
    expectancy_pct: float,
    config: Optional[StrategyPromotionConfig] = None
) -> StrategyPromotionDecision:
    """
    Apply promotion rules to a single preset's metrics.
    """
    if config is None:
        config = StrategyPromotionConfig()

    # Determine reliability
    reliability = "reliable" if trade_count >= config.min_trades_strong else "low_data"

    status: PromotionStatus = "REJECTED"

    # Rule 1: APPROVED
    # ALL must be true:
    # trade_count >= MIN_TRADES_STRONG
    # affinity_score >= 70
    # win_rate >= 0.52
    # max_drawdown_pct >= -0.30
    # expectancy_pct >= 0
    is_approved = (
        trade_count >= config.min_trades_strong and
        affinity_score >= config.min_score_approved and
        win_rate >= config.min_win_rate_approved and
        max_drawdown_pct >= config.max_dd_approved and
        expectancy_pct >= config.min_expectancy_approved
    )

    if is_approved:
        status = "APPROVED"
    else:
        # Rule 2: CANDIDATE
        # IF NOT APPROVED, but ALL true:
        # trade_count >= MIN_TRADES_WEAK
        # affinity_score >= 55
        # max_drawdown_pct >= -0.35
        is_candidate = (
            trade_count >= config.min_trades_weak and
            affinity_score >= config.min_score_candidate and
            max_drawdown_pct >= config.max_dd_candidate
        )
        
        if is_candidate:
            status = "CANDIDATE"
        else:
            # Rule 3: REJECTED (Fallback)
            status = "REJECTED"

    return StrategyPromotionDecision(
        preset_id=preset_id,
        affinity_score=affinity_score,
        grade=grade,
        trade_count=trade_count,
        win_rate=win_rate,
        net_pnl_pct=net_pnl_pct,
        max_drawdown_pct=max_drawdown_pct,
        expectancy_pct=expectancy_pct,
        reliability=reliability,
        status=status
    )

def compute_promotion_for_symbol(
    symbol: str, 
    affinity_data: dict, 
    scoreboard_data: dict, 
    config: Optional[StrategyPromotionConfig] = None
) -> StrategyPromotionSummary:
    """
    Compute promotion decisions for all strategies of a symbol.
    
    Args:
        symbol: The coin symbol (e.g. BTCUSDT)
        affinity_data: Dict loaded from sim_affinity.json. Expects 'presets' key.
        scoreboard_data: Dict of metrics. In Sim v1.2+, scoreboard results might be transient 
                        or re-derived. Here we assume we can pass a map of {preset_id: metrics_dict}.
                        Or better, use the structure from sim_affinity which already has most metrics!
                        
                        Wait, sim_affinity.json 'presets' ALREADY contains:
                        num_trades, win_rate, net_pnl_pct, expectancy_pct, max_drawdown_pct.
                        
                        So we technically ONLY need affinity_data. 
                        scoreboard_data is redundant if affinity_data is fresh.
                        
                        Let's use affinity_data as the source of truth if it has all metrics.
                        Reference: sim_affinity.py PresetAffinity dataclass has all fields.
    """
    if config is None:
        config = StrategyPromotionConfig()
        
    strategies = {}
    
    # Extract presets dict from affinity data
    # Structure: {'presets': {'PRESET_ID': {...fields...}}, ...}
    presets_dict = affinity_data.get('presets', {})
    
    for preset_id, data in presets_dict.items():
        # Handle both dict and object input (in case passed as object)
        if hasattr(data, 'affinity_score'): # It's an object
            d = data
            s_score = d.affinity_score
            s_grade = d.affinity_grade
            s_trades = d.num_trades
            s_win = d.win_rate
            s_pnl = d.net_pnl_pct
            s_dd = d.max_drawdown_pct
            s_exp = d.expectancy_pct
        else: # It's a dict
            s_score = data.get('affinity_score', 0)
            s_grade = data.get('affinity_grade', 'N/A')
            s_trades = data.get('num_trades', 0)
            s_win = data.get('win_rate', 0.0)
            s_pnl = data.get('net_pnl_pct', 0.0)
            s_dd = data.get('max_drawdown_pct', 0.0)
            s_exp = data.get('expectancy_pct', 0.0)

        decision = compute_promotion_for_preset(
            preset_id=preset_id,
            affinity_score=s_score,
            grade=s_grade,
            trade_count=s_trades,
            win_rate=s_win,
            net_pnl_pct=s_pnl,
            max_drawdown_pct=s_dd,
            expectancy_pct=s_exp,
            config=config
        )
        strategies[preset_id] = decision
        
    return StrategyPromotionSummary(
        symbol=symbol,
        rules_version="sim_promotion_v1",
        strategies=strategies,
        generated_at=datetime.now(timezone.utc).isoformat()
    )

def get_sim_promotion_path(symbol: str) -> Path:
    """Return path to sim_promotion.json."""
    return get_coin_profile_dir(symbol) / "sim_promotion.json"

def save_strategy_promotion(summary: StrategyPromotionSummary) -> None:
    """Save promotion summary to JSON."""
    out_path = get_sim_promotion_path(summary.symbol)
    
    data = asdict(summary)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Saved promotion profile for {summary.symbol} to {out_path}")

def load_sim_promotion(symbol: str) -> Optional[dict]:
    """Load promotion summary from JSON."""
    path = get_sim_promotion_path(symbol)
    if not path.exists():
        return None
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading promotion profile for {symbol}: {e}")
        return None
