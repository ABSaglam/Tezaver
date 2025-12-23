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

@dataclass
class TradeResultV2:
    """Result of a single simulated trade."""
    bundle_id: str
    symbol: str
    entry_ts: str
    exit_ts: Optional[str]
    entry_price: float
    exit_price: float
    pnl_pct: float
    duration_bars: int
    status: str # SUCCESS | HIT_SL | HIT_TP | TIMEOUT

@dataclass
class SniperBacktestReportV2:
    """Full backtest report for a bundle or bundle pack."""
    scenario_id: str
    symbol: str
    timeframe: str
    total_trades: int
    win_rate: float
    avg_pnl: float
    profit_factor: float
    trades: List[TradeResultV2] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)
    suggested_params: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def run_backtest_bundle(bundle_dir: str) -> Optional[TradeResultV2]:
    """
    Simulates a single trade based on bundle's approved entry and price window.
    """
    bundle_data = load_bundle_files(bundle_dir)
    manifest = bundle_data["manifest"]
    price_df = bundle_data["price_window"]
    
    if manifest is None or price_df is None or price_df.empty:
        return None
        
    symbol = manifest["symbol"]
    entry_ts = manifest["approved"]["entry_ts"]
    
    # Simple simulation: 
    # v1: Use approved_exit_ts if exists, else look for max gain in the window
    exit_ts = manifest["approved"].get("exit_ts")
    
    # Convert ts to match df format
    price_df['open_time'] = pd.to_datetime(price_df['open_time'])
    entry_dt = pd.to_datetime(entry_ts)
    
    # Normalize timezones
    if price_df['open_time'].dt.tz is not None and entry_dt.tz is None:
        entry_dt = entry_dt.tz_localize('UTC')
    elif price_df['open_time'].dt.tz is None and entry_dt.tz is not None:
        entry_dt = entry_dt.tz_localize(None)

    entry_row = price_df[price_df['open_time'] == entry_dt]
    if entry_row.empty:
        # Try finding nearest
        entry_row = price_df[price_df['open_time'] >= entry_dt].head(1)
        
    if entry_row.empty:
        return None
        
    entry_price = entry_row.iloc[0]['close']
    entry_idx = entry_row.index[0]
    
    if exit_ts:
        exit_dt = pd.to_datetime(exit_ts)
        # Normalize exit_dt
        if price_df['open_time'].dt.tz is not None and exit_dt.tz is None:
            exit_dt = exit_dt.tz_localize('UTC')
        elif price_df['open_time'].dt.tz is None and exit_dt.tz is not None:
            exit_dt = exit_dt.tz_localize(None)

        exit_row = price_df[price_df['open_time'] == exit_dt]
        if exit_row.empty:
            exit_row = price_df.iloc[-1:] # Fallback to last bar
    else:
        # No approved exit? Sniper finds best exit in window for feedback
        # Search for max high after entry
        future_df = price_df.loc[entry_idx+1:]
        if future_df.empty:
            exit_row = price_df.loc[entry_idx:entry_idx]
        else:
            best_idx = future_df['high'].idxmax()
            exit_row = future_df.loc[best_idx:best_idx]

    exit_price = exit_row.iloc[0]['close']
    exit_ts = exit_row.iloc[0]['open_time'].isoformat()
    
    pnl = (exit_price / entry_price - 1) * 100
    duration = int(exit_row.index[0] - entry_idx)
    
    return TradeResultV2(
        bundle_id=manifest["bundle_id"],
        symbol=symbol,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl_pct=pnl,
        duration_bars=duration,
        status="SUCCESS" if pnl > 0 else "FAIL"
    )

def analyze_pack_performance(scenario_id: str, bundles_root: str = ".tezaver_matrix/approved_bundles_v1") -> SniperBacktestReportV2:
    """
    Runs backtest for all bundles in a story pack.
    """
    from tezaver.foundry.bundle_index import scan_bundles
    df = scan_bundles(bundles_root)
    
    pack_df = df[df["scenario_id"] == scenario_id]
    if pack_df.empty:
        return SniperBacktestReportV2(scenario_id, "N/A", "N/A", 0, 0, 0, 0)
        
    trades = []
    for _, row in pack_df.iterrows():
        res = run_backtest_bundle(row["bundle_dir"])
        if res:
            trades.append(res)
            
    if not trades:
         return SniperBacktestReportV2(scenario_id, "N/A", "N/A", 0, 0, 0, 0)
         
    pnls = [t.pnl_pct for t in trades]
    wins = [1 for t in trades if t.pnl_pct > 0]
    losses = [t.pnl_pct for t in trades if t.pnl_pct < 0]
    
    win_rate = len(wins) / len(trades) * 100
    avg_pnl = np.mean(pnls)
    
    gross_profit = sum([t.pnl_pct for t in trades if t.pnl_pct > 0])
    gross_loss = abs(sum(losses)) if losses else 1.0
    profit_factor = gross_profit / gross_loss
    
    report = SniperBacktestReportV2(
        scenario_id=scenario_id,
        symbol=trades[0].symbol,
        timeframe=pack_df.iloc[0]["timeframe"],
        total_trades=len(trades),
        win_rate=win_rate,
        avg_pnl=avg_pnl,
        profit_factor=profit_factor,
        trades=trades
    )
    
    # Generate Feedback
    if avg_pnl < 5.0:
        report.feedback.append("Ortalama kazanç düşük. Giriş barı (entry_offset) çok geç olabilir.")
        report.suggested_params["entry_offset_delta"] = -2
    elif win_rate < 50:
        report.feedback.append("Başarı oranı düşük. Bu hikaye için daha sıkı bir Stop Loss veya farklı bir normalizasyon dene.")
    else:
        report.feedback.append("Hikaye başarılı görünüyor. War aşamasına geçilebilir.")

    return report
