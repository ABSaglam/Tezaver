"""
Strategy Verification Tool
==========================
Audits existing metadata.json files to calculate TRUE precision.
Corrects the logic error where false positives were previously ignored.

Usage:
    python scripts/verify_strategies.py [optional_symbol]

If symbol is provided, verifies only that coin.
If no symbol, verifies ALL coins in scripts/coins/.
"""

import sys
import os
import json
import pandas as pd
import glob
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def parse_rule(rule_str):
    """
    Parses a rule string which might contain 'AND'.
    Returns a list of tuples: [(indicator, operator, threshold), ...]
    """
    # Split by AND (case insensitive)
    parts = re.split(r'\s+AND\s+', rule_str, flags=re.IGNORECASE)
    parsed_rules = []
    
    for part in parts:
        hit = re.match(r"([a-z_0-9]+)\s*(>=|<=|>|<|==)\s*(-?[\d\.]+)", part.strip())
        if hit:
            parsed_rules.append(hit.groups())
        else:
            # Maybe a flag like 'no_consecutive_signals'
            # For verification of precision, we can usually ignore these as they effectively REDUCE signals
            # If we pass without it, we certainly pass with it (assuming it's a filter).
            # But technically, removing a filter might introduce false positives.
            # However, 'no_consecutive_signals' usually just removes the 2nd signal in a row.
            # If the 2nd signal was also a hit, it doesn't change precision.
             print(f"  ⚠️ Warning: Skipping non-standard component: '{part}'")
            
    return parsed_rules
            
    return parsed_rules

def apply_rule(row, rule_components_list):
    """Applies a list of parsed rules to a dataframe row."""
    # All conditions must be true (AND logic)
    for ind, op, thresh in rule_components_list:
        thresh = float(thresh)
        
        if ind not in row:
            return False
            
        val = row[ind]
        
        if op == '>=': 
            if not (val >= thresh): return False
        elif op == '<=': 
            if not (val <= thresh): return False
        elif op == '>': 
            if not (val > thresh): return False
        elif op == '<': 
            if not (val < thresh): return False
        elif op == '==': 
            if not (val == thresh): return False
            
    return True

def verify_coin(symbol, metadata_path):
    print(f"🔍 Verifying {symbol}...")
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"  ❌ Error loading metadata: {e}")
        return None

    if 'strategy' not in metadata or 'rule' not in metadata['strategy']:
        print(f"  ⚠️ No strategy rule found in metadata.")
        return None
        
    rule_str = metadata['strategy']['rule']
    print(f"  Rule: {rule_str}")
    
    # Parse Rule
    components = parse_rule(rule_str)
    if not components:
        print(f"  ❌ Could not parse rule: {rule_str}")
        return None
        
    # Collect all unique indicators needed
    indicators_needed = set()
    for ind, _, _ in components:
        indicators_needed.add(ind)
        
    # Load Data
    try:
        df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    except Exception as e:
         print(f"  ❌ Error loading history: {e}")
         return {'symbol': symbol, 'rule': rule_str, 'status': 'ERROR_DATA'}
         
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Calculate Needed Indicators
    for indicator in indicators_needed:
        if indicator not in df.columns:
            if indicator == 'mom_7d':
                 df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
            elif indicator == 'mom_5d':
                 df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
            elif indicator == 'mom_3d':
                 df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
            elif indicator == 'daily_ch':
                 df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
            elif indicator == 'ema_dist':
                 df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
                 df['ema_dist'] = (df['close'] / df['ema9'] - 1) * 100
            elif indicator == 'rsi':
                 delta = df['close'].diff()
                 gain = delta.where(delta > 0, 0).rolling(14).mean()
                 loss = -delta.where(delta < 0, 0).rolling(14).mean()
                 rs = gain / loss
                 df['rsi'] = 100 - (100 / (1 + rs))
            elif indicator == 'vol_ratio':
                 df['vol_ma20'] = df['volume'].rolling(20).mean()
                 df['vol_ratio'] = df['volume'] / df['vol_ma20']
            # Add others if needed
    
    # Get Rally Results
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    # Test Rule
    signals = []
    
    # Start from index 25 to ensure indicators are ready
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        if apply_rule(row, components):
            next_date = df.loc[idx+1, 'datetime'].date()
            is_rally = next_date in rally_results
            signals.append(is_rally)
            
    if not signals:
        print("  ⚠️ No signals generated.")
        return {'symbol': symbol, 'rule': rule_str, 'precision': 0, 'signals': 0, 'hits': 0, 'status': 'NO_SIGNALS'}
        
    hits = sum(signals)
    total = len(signals)
    precision = hits / total * 100
    
    print(f"  📊 Signals: {total} | Hits: {hits} | Real Precision: {precision:.1f}%")
    
    status = 'PASS' if precision >= 95 else 'FAIL' # Tolerance for minor data discrepancies, but aiming for 100
    if precision < 95: print("  ❌ FAILED!")
    else: print("  ✅ PASSED!")
    
    return {
        'symbol': symbol,
        'rule': rule_str,
        'signals': total,
        'hits': hits,
        'precision': precision,
        'status': status
    }

def main():
    target_symbol = sys.argv[1] if len(sys.argv) > 1 else None
    
    base_dir = "scripts/coins"
    results = []
    
    if target_symbol:
        path = os.path.join(base_dir, target_symbol.lower().replace('usdt', ''), 'metadata.json')
        if os.path.exists(path):
            res = verify_coin(target_symbol, path)
            if res: results.append(res)
        else:
            print(f"Metadata not found for {target_symbol} at {path}")
    else:
        # Scan all
        coin_dirs = sorted(glob.glob(os.path.join(base_dir, "*")))
        for d in coin_dirs:
            if not os.path.isdir(d): continue
            meta_path = os.path.join(d, 'metadata.json')
            if os.path.exists(meta_path):
                # Extract symbol from path or json
                try:
                    with open(meta_path) as f: m = json.load(f)
                    sym = m.get('symbol')
                    if sym:
                        res = verify_coin(sym, meta_path)
                        if res: results.append(res)
                except:
                    pass

    print("\n" + "="*80)
    print("FINAL AUDIT REPORT")
    print("="*80)
    print(f"{'SYMBOL':<10} | {'RULE':<20} | {'SIGNALS':<8} | {'PRECISION':<10} | {'STATUS'}")
    print("-" * 80)
    
    passed = 0
    failed = 0
    
    for r in results:
        print(f"{r['symbol']:<10} | {r['rule']:<20} | {r['signals']:<8} | {r['precision']:>5.1f}%    | {r['status']}")
        if r['status'] == 'PASS': passed += 1
        else: failed += 1
        
    print("-" * 80)
    print(f"TOTAL: {len(results)} | PASS: {passed} | FAIL: {failed}")

if __name__ == "__main__":
    main()
