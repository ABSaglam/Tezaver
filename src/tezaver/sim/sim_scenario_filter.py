"""
Sim Scenario Filter - Filter rallies by scenario type for targeted backtesting.

Enables scenario-specific performance analysis and simulation.
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from tezaver.rally.rally_narrative_engine import (
    analyze_scenario, 
    enrich_with_narratives, 
    SCENARIO_DEFINITIONS
)
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ScenarioStats:
    """Statistics for a single scenario."""
    scenario_id: str
    label: str
    risk: str
    count: int
    avg_gain_pct: float
    avg_quality: float
    win_rate_5p: float
    win_rate_10p: float
    avg_bars_to_peak: float


def get_all_scenario_ids() -> List[str]:
    """Return list of all scenario IDs."""
    return list(SCENARIO_DEFINITIONS.keys())


def get_scenario_info(scenario_id: str) -> Dict:
    """Get scenario definition info."""
    return SCENARIO_DEFINITIONS.get(scenario_id, {
        "label": "Bilinmeyen",
        "desc": "Tanımsız senaryo",
        "risk": "Medium"
    })


def filter_events_by_scenario(
    events_df: pd.DataFrame, 
    scenario_ids: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Filter events DataFrame by scenario type(s).
    
    Args:
        events_df: DataFrame with rally events
        scenario_ids: List of scenario IDs to include. None means all.
    
    Returns:
        Filtered DataFrame with scenario columns added
    """
    if events_df.empty:
        return events_df
    
    # Enrich with scenarios if not already done
    if 'scenario_id' not in events_df.columns:
        events_df = events_df.copy()
        events_df['scenario_id'] = events_df.apply(analyze_scenario, axis=1)
    
    # Apply filter
    if scenario_ids and len(scenario_ids) > 0:
        events_df = events_df[events_df['scenario_id'].isin(scenario_ids)]
    
    return events_df


def compute_scenario_stats(events_df: pd.DataFrame) -> Dict[str, ScenarioStats]:
    """
    Compute performance statistics grouped by scenario.
    
    Args:
        events_df: DataFrame with rally events (must have scenario_id column or will be computed)
    
    Returns:
        Dictionary of scenario_id -> ScenarioStats
    """
    if events_df.empty:
        return {}
    
    # Ensure scenario_id exists
    if 'scenario_id' not in events_df.columns:
        events_df = events_df.copy()
        events_df['scenario_id'] = events_df.apply(analyze_scenario, axis=1)
    
    stats = {}
    
    for scenario_id in events_df['scenario_id'].unique():
        scenario_events = events_df[events_df['scenario_id'] == scenario_id]
        info = get_scenario_info(scenario_id)
        
        # Calculate metrics
        gains = scenario_events['future_max_gain_pct'] * 100  # Convert to percentage
        qualities = scenario_events.get('quality_score', pd.Series([50] * len(scenario_events)))
        bars = scenario_events['bars_to_peak']
        
        # Win rates
        win_5p = (gains >= 5).sum() / len(gains) * 100 if len(gains) > 0 else 0
        win_10p = (gains >= 10).sum() / len(gains) * 100 if len(gains) > 0 else 0
        
        stats[scenario_id] = ScenarioStats(
            scenario_id=scenario_id,
            label=info.get('label', 'Bilinmeyen'),
            risk=info.get('risk', 'Medium'),
            count=len(scenario_events),
            avg_gain_pct=gains.mean() if len(gains) > 0 else 0,
            avg_quality=qualities.mean() if len(qualities) > 0 else 0,
            win_rate_5p=win_5p,
            win_rate_10p=win_10p,
            avg_bars_to_peak=bars.mean() if len(bars) > 0 else 0
        )
    
    return stats


def generate_scenario_report(events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a DataFrame report of scenario statistics.
    
    Args:
        events_df: DataFrame with rally events
    
    Returns:
        DataFrame with columns: Senaryo, Risk, Adet, Ort.Kazanç%, Ort.Kalite, %5+, %10+, Ort.Bar
    """
    stats = compute_scenario_stats(events_df)
    
    if not stats:
        return pd.DataFrame()
    
    rows = []
    for scenario_id, s in stats.items():
        rows.append({
            'Senaryo': s.label,
            'Risk': s.risk,
            'Adet': s.count,
            'Ort.Kazanç%': f'{s.avg_gain_pct:.1f}%',
            'Ort.Kalite': f'{s.avg_quality:.0f}',
            '%5+': f'{s.win_rate_5p:.0f}%',
            '%10+': f'{s.win_rate_10p:.0f}%',
            'Ort.Bar': f'{s.avg_bars_to_peak:.0f}'
        })
    
    report_df = pd.DataFrame(rows)
    
    # Sort by count descending
    if 'Adet' in report_df.columns:
        report_df = report_df.sort_values('Adet', ascending=False)
    
    return report_df


def get_best_scenario(events_df: pd.DataFrame, metric: str = 'win_rate_10p') -> Optional[str]:
    """
    Find the best performing scenario based on a metric.
    
    Args:
        events_df: DataFrame with rally events
        metric: 'win_rate_5p', 'win_rate_10p', 'avg_gain_pct', 'avg_quality'
    
    Returns:
        Best scenario ID or None
    """
    stats = compute_scenario_stats(events_df)
    
    if not stats:
        return None
    
    # Filter scenarios with at least 5 events
    valid_stats = {k: v for k, v in stats.items() if v.count >= 5}
    
    if not valid_stats:
        return None
    
    best = max(valid_stats.items(), key=lambda x: getattr(x[1], metric, 0))
    return best[0]
