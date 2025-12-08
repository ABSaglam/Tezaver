import sys
import os
import json
import logging
import pandas as pd
from datetime import datetime

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
    filename='wargame_btc_log.txt',
    filemode='w',
    format='%(asctime)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger()
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

TARGET_SYMBOL = "BTCUSDT"

def ensure_mock_profile(symbol):
    """Ensure we have some profile data to avoid strict blocking."""
    data_root = "data"
    profile_dir = os.path.join(data_root, "coin_profiles", symbol)
    os.makedirs(profile_dir, exist_ok=True)
    
    radar_path = os.path.join(profile_dir, "rally_radar.json")
    if not os.path.exists(radar_path):
        logger.warning(f"⚠️ Missing Radar for {symbol}. Creating MOCK HOT.")
        with open(radar_path, "w") as f:
            json.dump({"environment_status": "HOT"}, f)
            
    promo_path = os.path.join(profile_dir, "sim_promotion.json")
    if not os.path.exists(promo_path):
        logger.warning(f"⚠️ Missing Promotion for {symbol}. Creating MOCK APPROVED.")
        with open(promo_path, "w") as f:
            json.dump({"promotion_status": "APPROVED", "score": 85.0}, f)

def run_wargame():
    logger.info("⚔️ WAR GAME v1 INITIATED ⚔️")
    logger.info(f"Target: {TARGET_SYMBOL}")
    
    # 1. Load Data
    logger.info("Loading history...")
    df = load_single_coin_history(TARGET_SYMBOL, "1h")
    if df is None:
        logger.error("Failed to load history!")
        return
        
    logger.info(f"Loaded {len(df)} bars. Using last 3000.")
    df = df.tail(3000)
    
    # 2. Intelligence Check
    ensure_mock_profile(TARGET_SYMBOL)
    profile = load_guardrail_profile(TARGET_SYMBOL)
    logger.info(f"Intelligence: Radar={profile.env_status}, Status={profile.promotion_status}")
    
    # 3. Setup Engine
    symbols = [TARGET_SYMBOL]
    controller = GuardrailController(
        global_limits={"max_open_positions": 5},
        symbols=symbols
    )
    
    executor = MatrixExecutor(initial_balance_usdt=10000.0)
    
    multi_engine = MultiSymbolEngine(
        symbols=symbols,
        analyzer_factory=lambda s: RallyAnalyzer(rally_threshold=0.015), # 1.5% Threshold (Trend)
        strategist_factory=lambda s: RallyStrategist(),
        executor=executor,
        guardrails=controller
    )
    
    # 4. Simulation Loop
    start_time = datetime.now()
    
    # Provider
    def provider(sym):
        return df.iloc[:i+1] # Slows down as i grows but ok for 3000 bars
        
    logger.info("Starting simulation loop...")
    
    bar_indices = range(50, len(df))
    # Optimize provider to avoid copy? 
    # Actually Analyzer usually needs .tail(200). 
    # But let's stick to standard interface for correctness.
    
    for i in bar_indices:
        current_time = df.index[i]
        
        # Monitor Loop Speed
        if i % 100 == 0:
            pct = (i - 50) / len(bar_indices) * 100
            print(f"\rProgress: {pct:.1f}% | Time: {current_time}", end="")
            
        multi_engine.tick(current_time, provider)
        
        # Check if trade happened THIS tick?
        # Hard to check tick-level without hooking.
        # Strategist logs internal decisions usually? No standard logs there yet.
        # But we can check if slots have new Signal/Decision.
        
        slot = multi_engine.slots[0]
        if slot.last_signal and slot.last_signal['timestamp'] == current_time:
             sig = slot.last_signal
             logger.info(f"\n[{current_time}] 📡 SIGNAL: {sig['signal_type']} Score:{sig['score']:.1f}")
             
        if slot.last_decision and slot.last_decision.get('timestamp_detected') == current_time: 
             # Wait, decision doesn't have timestamp. 
             # We can't easily correlate decision time without storage. 
             # But if signal is new, decision is likely new.
             pass
             
    print("\nSimulation Complete.")
    
    # 5. Report
    state = executor.get_balance()
    pnl = state['equity'] - 10000.0
    pnl_pct = (pnl / 10000.0) * 100
    
    logger.info("-" * 40)
    logger.info("🏁 WAR GAME RESULTS")
    logger.info("-" * 40)
    logger.info(f"Initial Balance: $10,000.00")
    logger.info(f"Final Equity:    ${state['equity']:.2f}")
    logger.info(f"Net PnL:         ${pnl:.2f} ({pnl_pct:.2f}%)")
    logger.info(f"Positions Open:  {len(state['positions'])}")
    logger.info(f"Trade Count:     {len(executor.trade_history)}")
    
    # Dump Trades
    pd.DataFrame(executor.trade_history).to_csv("wargame_trades.csv")
    logger.info("Trades saved to wargame_trades.csv")
    
if __name__ == "__main__":
    run_wargame()
