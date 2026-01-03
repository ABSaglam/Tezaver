"""
Hard Negative Miner
===================

This script scans backtest reports for failed trades (False Positives) and exports them
as a dataset for "Active Learning" training.

Usage:
    python scripts/mine_hard_negatives.py --output hard_negatives.json
"""

import json
import logging
from pathlib import Path
from typing import List, Dict

# Add src to path
import sys
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from tezaver.core.logging_utils import get_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Miner")

RESULTS_DIR = project_root / ".tezaver_matrix" / "foundry" / "backtests"
VAULT_DIR = project_root / ".tezaver_matrix" / "vault" / "datasets"
VAULT_DIR.mkdir(parents=True, exist_ok=True)

def mine_trades(min_pnl_loss: float = 0.0) -> List[Dict]:
    """Scan all backtest JSONs and extract losing trades."""
    hard_negatives = []
    
    reports = list(RESULTS_DIR.glob("backtest_*.json"))
    logger.info(f"Scanning {len(reports)} reports...")
    
    for report_path in reports:
        try:
            with open(report_path, 'r') as f:
                data = json.load(f)
                
            symbol = data.get('symbol')
            trades = data.get('trades', [])
            
            if not trades:
                continue
                
            count = 0
            for t in trades:
                pnl = t.get('pnl', 0)
                if pnl < -min_pnl_loss: # Strict loss
                    # This is a False Positive!
                    entry_time = t.get('entry_time')
                    hard_negatives.append({
                        "symbol": symbol,
                        "timeframe": "15m", # Hardcoded for now as backtest was 15m
                        "timestamp": entry_time,
                        "pnl": pnl,
                        "reason": "backtest_false_positive"
                    })
                    count += 1
            
            if count > 0:
                logger.info(f"Found {count} hard negatives in {symbol}")
                
        except Exception as e:
            logger.error(f"Error reading {report_path}: {e}")
            
    return hard_negatives

def main():
    logger.info("Starting Hard Negative Mining...")
    
    negatives = mine_trades()
    
    if not negatives:
        logger.warning("No hard negatives found! (Did backtest save trades?)")
        return
        
    output_path = VAULT_DIR / "hard_negatives_v1.json"
    
    with open(output_path, 'w') as f:
        json.dump(negatives, f, indent=2)
        
    logger.info(f"Mining Complete. Saved {len(negatives)} samples to {output_path}")

if __name__ == "__main__":
    main()
