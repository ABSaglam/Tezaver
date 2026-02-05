import sys
import os
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add current directory to path to import local modules
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

import utils_io
import v17_schema

# --- CONFIG ---
SYMBOL = "AVAXUSDT"
TRAIN_START = pd.Timestamp("2023-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2025-12-31", tz="UTC")
ROLLING_WINDOW_LONG = 365 # days
ROLLING_WINDOW_SHORT = 90 # days (recent context)

def calculate_technical_features(df_daily, df_4h, df_1h, df_15m):
    """
    Calculates technical features for V17.
    CRITICAL: Feature at index t must ONLY use data up to t.
    """
    # Create copy to avoid mutating original
    df = df_daily.copy()
    
    # 1. Structural DNA (ADX, ATR, Angles)
    # ATR
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
    df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr_14'] = df['tr'].rolling(14).mean()
    df['ATR_Norm'] = df['atr_14'] / df['close']
    
    # ADX (Simplified implementation for robust standalone calc)
    up = df['high'] - df['high'].shift(1)
    down = df['low'].shift(1) - df['low']
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    df['plus_di'] = 100 * pd.Series(plus_dm).rolling(14).mean() / df['atr_14']
    df['minus_di'] = 100 * pd.Series(minus_dm).rolling(14).mean() / df['atr_14']
    df['dx'] = 100 * np.abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['ADX'] = df['dx'].rolling(14).mean()
    
    # Structure Angles / EMA Dist
    df['ema_20'] = df['close'].ewm(span=20).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['Dist_EMA'] = (df['close'] - df['ema_20']) / df['ema_20']
    
    # Ang_EMA: Slope of EMA20 over last 3 days
    df['Ang_EMA'] = (df['ema_20'] - df['ema_20'].shift(3)) / df['ema_20'].shift(3) * 100
    
    # Ang_Price: Linear regression slope of last 5 closes (normalized)
    def linear_slope(y):
        if len(y) < 5: return 0.0
        x = np.arange(len(y))
        return np.polyfit(x, y, 1)[0] / y.mean() * 100
    
    df['Ang_Price'] = df['close'].rolling(5).apply(linear_slope, raw=True)
    
    # Wick Ratio (Upper Wick / Total Range)
    # Upper Wick = High - max(Open, Close)
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['total_range'] = df['high'] - df['low']
    df['Wick_Ratio'] = df['upper_wick'] / (df['total_range'] + 1e-9) # Avoid div/0
    
    # 2. Energy & Momentum
    # Vrsi (Volume RSI) - Simplified
    # Up volume is volume when close > prev_close
    df['vol_up'] = np.where(df['close'] > df['close'].shift(1), df['volume'], 0)
    df['vol_down'] = np.where(df['close'] <= df['close'].shift(1), df['volume'], 0)
    df['w_vol_up'] = df['vol_up'].rolling(14).mean()
    df['w_vol_down'] = df['vol_down'].rolling(14).mean()
    df['Vrsi'] = 100 - (100 / (1 + df['w_vol_up'] / (df['w_vol_down'] + 1e-9)))
    
    # V-Mom (Volume Momentum)
    # (Vol / MA_Vol_10) - 1
    df['vol_ma_10'] = df['volume'].rolling(10).mean()
    df['V-Mom'] = (df['volume'] / df['vol_ma_10']) - 1
    
    # Vol_Ratio (Relative Volatility)
    # StdDev(5) / StdDev(20)
    df['Vol_Ratio'] = df['close'].rolling(5).std() / (df['close'].rolling(20).std() + 1e-9)
    
    # Volt_Ratio (ATR / Rolling ATR Mean) - "Volatility Expansion Ratio"
    df['Volt_Ratio'] = df['atr_14'] / (df['atr_14'].rolling(30).mean() + 1e-9)
    
    # Energy_Gap
    # Difference between Price RSI and Volume RSI
    def rsi_calc(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))
        
    df['rsi_14'] = rsi_calc(df['close'])
    df['Energy_Gap'] = df['rsi_14'] - df['Vrsi'] # Positive means Price > Vol (Potential Exhaustion or drift)
    
    # 3. Rolling DNA & Drift Factor
    # Rolling stats for last 365 days (approx 365 bars)
    # Drift = Euclidean distance of normalized features to rolling median
    # We will pick 3 key features for drift: ADX, ATR_Norm, Vrsi
    # Normalize simply by dividing by rolling median
    
    cols_for_drift = ['ADX', 'ATR_Norm', 'Vrsi']
    for c in cols_for_drift:
        df[f'rolling_med_{c}'] = df[c].rolling(365, min_periods=30).median()
    
    df['drift_sq_sum'] = 0
    for c in cols_for_drift:
        ratio = df[c] / (df[f'rolling_med_{c}'] + 1e-9) - 1
        df['drift_sq_sum'] += ratio ** 2
        
    df['Drift_Factor'] = np.sqrt(df['drift_sq_sum'])
    
    # Anti_Penalty (Placeholder logic - requires complex anti-pattern matching which is out of scope for "Basic" script, 
    # but we will simulate it with a simple heuristic: High drift + Low vol = Penalty)
    df['Anti_Penalty'] = df['Drift_Factor'] * (1 / (df['Volt_Ratio'] + 1e-9))
    
    # 4. Trigger Placeholders (These essentially come from 15M/1H lookups, but we compute aggregates here)
    # We need to map 15M aggregates to Daily bars.
    # Since we are "Learning", we can do a lookup.
    # For now, default values (will be refined in detailed loop)
    df['Micro_Trig'] = False
    df['Ignition_Type'] = "NONE"
    df['M15_RSI'] = 50.0 # Neural
    df['M15_Vol'] = 1.0  # Neural
    
    return df

def generate_labels(df):
    """
    Generates labels based on t+1 Price Action.
    Hit_10 = YES if (Max_Excursion >= 10%)
    """
    # Max Excursion: Max High of T+1 / Close of T - 1
    df['next_high'] = df['high'].shift(-1)
    df['next_close'] = df['close'].shift(-1)
    df['next_low'] = df['low'].shift(-1)
    
    df['Max_Excursion'] = (df['next_high'] / df['close'] - 1) * 100
    df['Close_Excursion'] = (df['next_close'] / df['close'] - 1) * 100
    df['Drawdown'] = (df['next_low'] / df['close'] - 1) * 100
    
    df['Hit_10'] = np.where(df['Max_Excursion'] >= 10.0, "YES", "NO")
    
    return df

def run_learning_phase():
    print("::: Loading Data :::")
    data_bundle = utils_io.get_data_bundle(SYMBOL)
    df_daily = data_bundle['1d']
    df_15m = data_bundle['15m']
    
    print(f"Daily Rows: {len(df_daily)}")
    
    # 1. Feature Engineering
    print("::: V17 Feature Generation :::")
    df_feat = calculate_technical_features(df_daily, None, None, None)
    
    # 2. Labeling (Anti-Hindsight check: shift(-1) used only here)
    df_labeled = generate_labels(df_feat)
    
    # 3. Filter Training Set
    mask_train = (df_labeled['datetime'] >= TRAIN_START) & (df_labeled['datetime'] <= TRAIN_END)
    df_train = df_labeled[mask_train].copy()
    
    print(f"Training Data Size: {len(df_train)} days")
    print(f"Hit_10 Rates in Train: {df_train['Hit_10'].value_counts()}")
    
    # 4. FAIL-FIRST LEARNING (Hard Veto)
    # Analyze NO days vs YES days intervals
    fail_rules = {}
    cols_to_check = ['Wick_Ratio', 'Dist_EMA', 'ATR_Norm', 'Energy_Gap', 'Anti_Penalty', 'Drift_Factor']
    
    df_yes = df_train[df_train['Hit_10'] == "YES"]
    df_no = df_train[df_train['Hit_10'] == "NO"]
    
    print(f"\n--- LEARNING FAIL ZONES ({len(df_no)} FAIL samples) ---")
    
    for col in cols_to_check:
        # Determine Safe Zone from YES samples (e.g., 5th to 95th percentile)
        # We want to veto things that are very common in FAIL but rare/absent in YES.
        # Strategy: Find min/max of YES. Anything outside is risky.
        # But we need "Dense Fail Zones".
        
        # Simple Logic: Veto if Value < min(YES) or Value > max(YES)
        # But allow 2% tolerance
        min_yes = df_yes[col].quantile(0.02)
        max_yes = df_yes[col].quantile(0.98)
        
        # Check effectiveness: How many NOs do we catch?
        caught_low = df_no[df_no[col] < min_yes]
        caught_high = df_no[df_no[col] > max_yes]
        
        veto_rule = {}
        if len(caught_low) > 5: # At least 5 incidents
            veto_rule['min_hard'] = float(min_yes)
        
        if len(caught_high) > 5:
            veto_rule['max_hard'] = float(max_yes)
            
        if veto_rule:
            fail_rules[col] = veto_rule
            print(f"Rule learned for {col}: {veto_rule}")

    # 5. SUCCESS CORRIDOR
    print("\n--- LEARNING SUCCESS CORRIDOR ---")
    # Tighter bands for GOLD/DIAMOND
    success_corridor = {}
    
    # Score logic: we don't have a pre-computed score yet, so we define one based on basic metrics
    # For now, we learn bands for Energy_Gap and ATR_Norm from the YES set (p25-p75 is too strict, let's use p10-p90)
    
    for col in ['ATR_Norm', 'Energy_Gap']:
        p10 = df_yes[col].quantile(0.10)
        p90 = df_yes[col].quantile(0.90)
        success_corridor[col] = {"min": float(p10), "max": float(p90)}
        
    print(f"Success Corridor: {success_corridor}")
    
    # 6. INTRADAY CANCEL (Placeholder for now - requires complex intraday matching)
    intraday_cancel = {
        "cancel_conditions": [
            {"type": "4H_VMom_Spike_Fade", "threshold": 2.5},
            {"type": "1H_Wick_Expansion", "threshold": 0.05}
        ]
    }
    
    # 7. TRIGGER MAP (Placeholder)
    trigger_map = {
        "whitelisted_ignitors": ["BULLISH_ENGULFING", "HAMMER"],
        "m15_vol_threshold": 2.0
    }
    
    # SAVE RULES
    out_dir = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn/rules")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    utils_io.save_json_rule(fail_rules, out_dir / "avax_fail_rules.json")
    utils_io.save_json_rule(success_corridor, out_dir / "avax_success_corridor.json")
    utils_io.save_json_rule(intraday_cancel, out_dir / "avax_intraday_cancel_rules.json")
    utils_io.save_json_rule(trigger_map, out_dir / "avax_trigger_map.json")
    
    print(f"\nRules saved to {out_dir}")

if __name__ == "__main__":
    run_learning_phase()
