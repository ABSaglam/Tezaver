"""
Tezaver Sim v1.2 - Preset Scoreboard
====================================

Orchestrates running multiple simulation presets for a symbol and aggregating results.
"""

from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional
import pandas as pd
import logging

from tezaver.sim import sim_engine, sim_presets
from tezaver.sim.sim_config import RallySimConfig

logger = logging.getLogger(__name__)

@dataclass
class PresetScore:
    """
    Summary metrics for a specific preset's performance.
    """
    preset_id: str
    preset_label_tr: str
    timeframe: str
    num_trades: int
    win_rate: float
    net_pnl_pct: float
    max_drawdown_pct: float
    expectancy_pct: float     # Converted from R to % if needed, or kept as is
    avg_hold_bars: float
    sim_period_days: Optional[float] = None

def run_preset_scoreboard(symbol: str, preset_ids: Optional[List[str]] = None) -> Tuple[List[PresetScore], List[str]]:
    """
    Run simulations for all (or specified) presets for the given symbol.
    
    Returns:
        scores: List of PresetScore objects for successful runs.
        errors: List of preset_ids that failed.
    """
    scores = []
    errors = []
    
    if preset_ids is None:
        all_presets = sim_presets.get_all_presets()
    else:
        all_presets = []
        for pid in preset_ids:
            p = sim_presets.get_preset_by_id(pid)
            if p:
                all_presets.append(p)
            else:
                logger.warning(f"Preset ID not found: {pid}")
                
    for preset in all_presets:
        try:
            # 1. Build Config
            cfg = sim_presets.build_config_from_preset(preset, symbol)
            
            # 2. Key Data Loading (Optimized if done outside loop? Engine handles it per call)
            # Just let engine handle it for simplicity now in v1.2
            events_df = sim_engine.load_rally_events(symbol, cfg.timeframe)
            prices_df = sim_engine.load_price_series(symbol, cfg.timeframe)
            
            if events_df.empty or prices_df.empty:
                # Not necessarily an error, just no data.
                # But treating as "no score"
                logger.info(f"No data for preset {preset.id} ({symbol}/{cfg.timeframe})")
                continue
                
            # 3. Filter & Simulate
            filtered_events = sim_engine.filter_events(events_df, cfg)
            
            if filtered_events.empty:
                 # Create zero-score entry
                 score = PresetScore(
                    preset_id=preset.id,
                    preset_label_tr=preset.label_tr,
                    timeframe=preset.timeframe,
                    num_trades=0,
                    win_rate=0.0,
                    net_pnl_pct=0.0,
                    max_drawdown_pct=0.0,
                    expectancy_pct=0.0,
                    avg_hold_bars=0.0,
                    sim_period_days=0.0
                 )
                 scores.append(score)
                 continue
                 
            trades_df, equity_df = sim_engine.simulate_trades(filtered_events, prices_df, cfg)
            
            # 4. Summarize
            results = sim_engine.summarize_results(trades_df, equity_df, preset_id=preset.id)
            
            # Helper for duration
            sim_days = 0.0
            if not prices_df.empty:
                delta = prices_df.index[-1] - prices_df.index[0]
                sim_days = delta.total_seconds() / 86400.0
                
            # Helper for avg holding
            avg_hold = 0.0
            if not trades_df.empty:
                # We don't have bar counts in trade log directly, but can infer from timestamps?
                # Actually trade list has 'entry_time', 'exit_time'.
                # But simpler is if engine returned it. 
                # Let's approximate using rough bar duration math or just 0 for now if complex.
                # Actually, let's verify if engine exposes hold bars. It does not.
                # Let's calculate from timestamps roughly.
                deltas = (trades_df['exit_time'] - trades_df['entry_time']).dt.total_seconds()
                # Need timeframe duration in seconds
                tf_secs = 3600 # default 1h
                if '15m' in cfg.timeframe: tf_secs = 900
                elif '4h' in cfg.timeframe: tf_secs = 14400
                elif '1d' in cfg.timeframe: tf_secs = 86400
                
                avg_hold = (deltas / tf_secs).mean()

            score = PresetScore(
                preset_id=preset.id,
                preset_label_tr=preset.label_tr,
                timeframe=preset.timeframe,
                num_trades=results['num_trades'],
                win_rate=results['win_rate'],
                net_pnl_pct=results['total_pnl_pct'],
                max_drawdown_pct=results['max_drawdown_pct'],
                expectancy_pct=float(results['expectancy_R']) * 100, # Assuming expectancy_R is raw decimal
                avg_hold_bars=float(avg_hold),
                sim_period_days=sim_days
            )
            scores.append(score)
            
        except Exception as e:
            logger.error(f"Error running preset {preset.id}: {e}", exc_info=True)
            errors.append(preset.id)
            
    return scores, errors

def scores_to_dataframe(scores: List[PresetScore]) -> pd.DataFrame:
    """
    Convert list of PresetScore to DataFrame.
    """
    if not scores:
        return pd.DataFrame()
    return pd.DataFrame([asdict(s) for s in scores])

# --- Affinity Integration ---

def generate_affinity_for_symbol(
    symbol: str,
    cfg: Optional['AffinityConfig'] = None,
) -> 'StrategyAffinitySummary':
    """
    Run full scoreboard for symbol, compute affinity, and export JSON.
    """
    from tezaver.sim.sim_affinity import (
        AffinityConfig,
        compute_strategy_affinity,
        save_strategy_affinity,
        StrategyAffinitySummary
    )

    # 1. Run Scoreboard
    scores, errors = run_preset_scoreboard(symbol)
    
    # 2. Compute Affinity
    summary = compute_strategy_affinity(scores, symbol, cfg)
    
    # 3. Save Affinity
    save_strategy_affinity(symbol, summary)
    
    # 4. [NEW] Sim v1.5 Promotion
    try:
        from tezaver.sim.sim_promotion import compute_promotion_for_symbol, save_strategy_promotion
        # affinity data as dict (summary converted to dict first? Or allow summary object?)
        # compute_promotion_for_symbol expects dict for affinity_data in current signature
        # Let's fix signature or cast summary to dict
        affinity_dict = asdict(summary)
        promo_summary = compute_promotion_for_symbol(symbol, affinity_dict, {})
        save_strategy_promotion(promo_summary)
    except Exception as e:
        logger.error(f"Error executing Sim v1.5 Promotion logic for {symbol}: {e}", exc_info=True)

    return summary

