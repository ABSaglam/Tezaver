"""
Sniper Backtest V2 - Feedback & Refinement Engine
=================================================

Runs historical simulations for Story Packs and provides feedback to Foundry.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from tezaver.core import coin_cell_paths
from tezaver.foundry.bundle_index import load_bundle_files

from tezaver.sniper.sniper_backtest import run_sniper_backtest_from_trade_ids
from tezaver.sniper.sniper_ids import make_trade_id

@dataclass
class SniperBacktestReportV2:
    """Full backtest report for a bundle or bundle pack."""
    scenario_id: str
    symbol: str
    timeframe: str
    total_trades: int
    win_rate: float
    pnl_pct: float
    max_drawdown: float
    trades: List[Dict[str, Any]] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)
    suggested_params: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def analyze_pack_performance(scenario_id: str, bundles_root: str = ".tezaver_matrix/approved_bundles_v1") -> SniperBacktestReportV2:
    """
    Runs professional backtest for all bundles in a story pack using Matrix Sniper engine.
    """
    from tezaver.foundry.bundle_index import scan_bundles
    df = scan_bundles(bundles_root)
    
    if df.empty or "scenario_id" not in df.columns:
        return SniperBacktestReportV2(scenario_id, "N/A", "N/A", 0, 0, 0, 0)
        
    pack_df = df[df["scenario_id"] == scenario_id]
    if pack_df.empty:
        return SniperBacktestReportV2(scenario_id, "N/A", "N/A", 0, 0, 0, 0)
        
    # Collect trade_ids from bundles
    trade_ids = []
    symbol = pack_df.iloc[0]["symbol"]
    timeframe = pack_df.iloc[0]["timeframe"]
    
    # Load analytics dataset to resolve true trade_ids (which include event_idx + ts)
    from tezaver.sniper.sniper_backtest import _get_sniper_entries_path
    from tezaver.sniper.sniper_ids import ensure_trade_id_column
    
    analytics_path = _get_sniper_entries_path(symbol, timeframe)
    if not analytics_path.exists():
        report = SniperBacktestReportV2(scenario_id, symbol, timeframe, 0, 0, 0, 0)
        report.feedback.append(f"Analitik veri seti bulunamadı: {analytics_path}")
        return report
    
    analytics_df = pd.read_parquet(analytics_path)
    # Normalize event_time to string for robust comparison (YYYY-MM-DD HH:MM:SS)
    if "event_time" in analytics_df.columns:
        analytics_df["event_time_str"] = pd.to_datetime(analytics_df["event_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    
    analytics_df = ensure_trade_id_column(analytics_df)
    
    trade_ids = []
    for _, row in pack_df.iterrows():
        bundle_event_id = str(row["event_id"])
        bundle_ts_str = pd.to_datetime(row["event_time_iso"]).strftime("%Y-%m-%d %H:%M:%S")
        
        # Try finding the trade_id in analytics_df
        match = analytics_df[analytics_df["trade_id"].str.contains(bundle_event_id, na=False)]
        
        if match.empty and "event_time_str" in analytics_df.columns:
            # Fallback: match by normalized timestamp string
            match = analytics_df[analytics_df["event_time_str"] == bundle_ts_str]
            
        if not match.empty:
            trade_ids.append(match.iloc[0]["trade_id"])
            
    if not trade_ids:
         report = SniperBacktestReportV2(scenario_id, symbol, timeframe, 0, 0, 0, 0)
         report.feedback.append("Bundle'lar analitik veri setinde eşleştirilemedi.")
         return report
    
    # Run Arena-grade backtest
    try:
        results = run_sniper_backtest_from_trade_ids(
            symbol=symbol,
            timeframe=timeframe,
            selected_trade_ids=trade_ids,
            risk=0.01,
            tp_pct=0.08,
            sl_pct=0.03,
            max_horizon_bars=20
        )
    except Exception as e:
        # Fallback for missing datasets etc.
        report = SniperBacktestReportV2(scenario_id, symbol, timeframe, 0, 0, 0, 0)
        report.feedback.append(f"Backtest hatası: {str(e)}")
        return report
         
    report = SniperBacktestReportV2(
        scenario_id=scenario_id,
        symbol=symbol,
        timeframe=timeframe,
        total_trades=results["trades"],
        win_rate=results["win_rate"],
        pnl_pct=results["pnl_pct"],
        max_drawdown=results["max_drawdown_pct"],
        trades=results["ledger"]
    )
    
    # Generate Feedback based on professional results
    if report.pnl_pct < 1.0:
        report.feedback.append("Performans zayıf. Desenler arası zaman farkı (interval) optimize edilmeli.")
        report.suggested_params["notional_multiplier"] = 0.5
    elif report.win_rate < 40:
        report.feedback.append("Başarı oranı çok düşük. Bu hikaye için filtreler (entry_filters) çok gevşek olabilir.")
    else:
        report.feedback.append("Profesyonel backtest sonuçları başarılı. Matrix War havuzuna güvenle sürülebilir.")

    return report
