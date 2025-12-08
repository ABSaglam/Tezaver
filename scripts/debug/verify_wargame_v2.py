import sys
import os
import json
import logging
import pandas as pd
from datetime import datetime
from collections import defaultdict

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tezaver.engine.matrix_executor import MatrixExecutor
from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer
from tezaver.engine.strategists.rally_strategist import RallyStrategist
from tezaver.matrix.multi_symbol_engine import MultiSymbolEngine
from tezaver.matrix.guardrail import GuardrailController, load_guardrail_profile
from tezaver.data.history_loader import load_single_coin_history

# Setup Logging
logging.basicConfig(
    filename='wargame_v2_log.txt',
    filemode='w',
    format='%(asctime)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger()
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

TARGET_COINS = ["BTCUSDT"]  # Can add ETH later

def create_mock_profiles():
    """Create controlled scenarios for War Game v2."""
    data_root = "data"
    
    # 1. BTCUSDT -> HOT + APPROVED (Should Trade)
    # Actually, we rely on existing data? No, for "verify" we want specific test cases.
    # But user asked to use REAL data if possible.
    # Let's check if we have data. If not, create mock.
    # For now, let's FORCE mock for test determinism or rely on current state?
    # War Game v1 results showed static HOT caused losses.
    # Let's set BTC to something safe or risky to test guardrail.
    
    # Let's simulate a strict scenario:
    # BTC -> COLD (Should Block Rallies)
    
    # Wait, we want to verify blocking.
    # Let's set BTC to COLD for the first half, then HOT?
    # No, profiles are static on disk for now (unless we reload).
    
    # Let's verify Block Logic specifically.
    pass

def ensure_profile(symbol, env="HOT", status="APPROVED", score=80.0):
    """Force a specific profile to disk."""
    profile_dir = os.path.join("data", "coin_profiles", symbol)
    os.makedirs(profile_dir, exist_ok=True)
    
    with open(os.path.join(profile_dir, "rally_radar.json"), "w") as f:
        json.dump({"environment_status": env}, f)
        
    with open(os.path.join(profile_dir, "sim_promotion.json"), "w") as f:
        json.dump({"promotion_status": status, "score": score}, f)
        
    logger.info(f"⚡ [SETUP] {symbol} Profile -> Env:{env} Status:{status} Score:{score}")

def run_wargame_v2():
    logger.info("⚔️ WAR GAME v2: GUARDRAILS ON ⚔️")
    
    # TEST SCENARIO: 
    # BTCUSDT => COLD env => Should BLOCK all trades.
    # ETHUSDT => HOT + REJECTED => Should BLOCK all trades.
    # SOLUSDT => HOT + APPROVED + Score 90 => Should ALLOW.
    
    # Let's assume we have history for these. If not, we skip.
    symbols_to_test = ["BTCUSDT", "ETHUSDT", "SOLUSDT"] 
    # Check history availability
    valid_symbols = []
    
    data_map = {}
    
    for sym in symbols_to_test:
        df = load_single_coin_history(sym, "1h")
        if df is not None:
             df = df.tail(1000) # 1000 bars
             data_map[sym] = df
             valid_symbols.append(sym)
        else:
            logger.warning(f"⚠️ No history for {sym}, skipping.")
            
    if not valid_symbols:
        logger.error("No valid symbols found!")
        return

    # Setup Scenarios manually
    if "BTCUSDT" in valid_symbols:
        ensure_profile("BTCUSDT", env="COLD", status="APPROVED") # Block Radar
    if "ETHUSDT" in valid_symbols:
        ensure_profile("ETHUSDT", env="HOT", status="REJECTED") # Block Strategy
    if "SOLUSDT" in valid_symbols:
        ensure_profile("SOLUSDT", env="HOT", status="APPROVED", score=95) # Allow
    elif "AVAXUSDT" in valid_symbols: # Fallback if SOL missing
        ensure_profile("AVAXUSDT", env="HOT", status="APPROVED", score=95)
        
    symbols = valid_symbols
    
    logger.info(f"Fleet: {symbols}")
    
    # Setup Engine
    controller = GuardrailController(
        global_limits={"max_open_positions": 5},
        symbols=symbols
    )
    
    executor = MatrixExecutor(initial_balance_usdt=50000.0)
    
    multi_engine = MultiSymbolEngine(
        symbols=symbols,
        analyzer_factory=lambda s: RallyAnalyzer(rally_threshold=0.015), 
        strategist_factory=lambda s: RallyStrategist(),
        executor=executor,
        guardrails=controller
    )
    
    # Stats
    guardrail_stats = defaultdict(int)
    total_signals = 0
    
    # Loop
    logger.info("Starting simulation...")
    
    # Pre-calc dates (assuming alignment)
    # Using BTC/first as master clock
    ref_sym = symbols[0]
    ref_df = data_map[ref_sym]
    
    for i in range(50, len(ref_df)):
        current_time = ref_df.index[i]
        
        def provider(sym):
            if sym not in data_map: return None
            # Need to align timestamps perfectly? 
            # Simplified: just slice 0..i assuming aligned indices if simple history loading
            # But different coins might have different start dates.
            # Best effort: use timestamp indexing
            d = data_map[sym]
            return d.loc[:current_time] 
            
        multi_engine.tick(current_time, provider)
        
        # Check slots for updates
        for slot in multi_engine.slots:
            # Check Signal
            if slot.last_signal and slot.last_signal['timestamp'] == current_time:
                 total_signals += 1
                 # Check what happened
                 
                 # Guardrail Decision? (Available via logic we added)
                 g_decision = slot.last_guardrail_decision
                 
                 # If executed?
                 # Unified Engine doesn't give us "Decision was BLOCKED" easily,
                 # but we know if Guardrail said BLOCK, Strategist returned None.
                 
                 # Logic: 
                 # If Signal Exists AND Guardrail Decision is fresh?
                 # Guardrail is checked inside Strategist.evaluate(), called inside UnifiedEngine.
                 # So if signal, evaluate() was called -> callback fired -> last_guardrail_decision updated.
                 
                 # We need to verify if g_decision is FRESH.
                 # Actually, we don't have timestamp on g_decision. 
                 # But it's updated synchronously in this tick.
                 # So we presume it corresponds to this signal.
                 
                 if g_decision:
                     code = g_decision.reason_code
                     allow = g_decision.allow
                     guardrail_stats[code] += 1
                     
                     icon = "✅" if allow else "🛑"
                     logger.info(f"[{current_time}] {slot.symbol} Signal Score:{slot.last_signal['score']:.1f} -> {icon} {code}")
                 else:
                     logger.info(f"[{current_time}] {slot.symbol} Signal but NO Guardrail Decision??")
                     
    
    # Report
    logger.info("-" * 40)
    logger.info("🏁 WAR GAME v2 RESULTS")
    logger.info("-" * 40)
    logger.info(f"Total Signals Detected: {total_signals}")
    logger.info("Guardrail Decisions:")
    for code, count in guardrail_stats.items():
        logger.info(f"  - {code}: {count}")
        
    state = executor.get_balance()
    pnl = state['equity'] - 50000.0
    
    logger.info("-" * 40)
    logger.info(f"Net PnL: ${pnl:.2f}")
    logger.info(f"Trades Opened: {len(state['positions'])}")
    logger.info(f"Trade History: {len(executor.trade_history)}")

    # Specific Verification
    # BTC (COLD) should have 0 trades? Or checking signals blocked.
    pass

if __name__ == "__main__":
    run_wargame_v2()
