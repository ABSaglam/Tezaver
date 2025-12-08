import sys
import os
import json
import shutil
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tezaver.engine.matrix_executor import MatrixExecutor
from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer
from tezaver.engine.strategists.rally_strategist import RallyStrategist
from tezaver.matrix.multi_symbol_engine import MultiSymbolEngine
from tezaver.matrix.guardrail import GuardrailController

def setup_mock_profile(symbol, radar="HOT", promo="APPROVED"):
    path = os.path.join("data", "coin_profiles", symbol)
    os.makedirs(path, exist_ok=True)
    
    with open(os.path.join(path, "rally_radar.json"), "w") as f:
        json.dump({"environment_status": radar}, f)
        
    with open(os.path.join(path, "sim_promotion.json"), "w") as f:
        json.dump({"promotion_status": promo, "score": 85.0}, f)

def verify_fusion():
    print(">>> M25.4 Guardrail Fusion Verification <<<")
    
    # 1. Setup Mock Intelligence
    test_coins = ["G_OK", "G_COLD", "G_REJECTED"]
    
    setup_mock_profile("G_OK", radar="HOT", promo="APPROVED")
    setup_mock_profile("G_COLD", radar="COLD", promo="APPROVED")
    setup_mock_profile("G_REJECTED", radar="HOT", promo="REJECTED")
    
    # 2. Mock Market Data (All Exploding -> Signal Generated)
    dates = pd.date_range(start="2024-01-01", periods=60, freq="1h")
    prices = [100.0] * 50 + [100.0 * (1.05**i) for i in range(10)]
    df = pd.DataFrame({"close": prices, "high": prices, "low": prices}, index=dates)
    
    # 3. Setup Fleet
    executor = MatrixExecutor(initial_balance_usdt=50000)
    controller = GuardrailController(
        global_limits={"max_open_positions": 5},
        symbols=test_coins
    )
    
    multi_engine = MultiSymbolEngine(
        symbols=test_coins,
        analyzer_factory=lambda s: RallyAnalyzer(rally_threshold=0.01),
        strategist_factory=lambda s: RallyStrategist(),
        executor=executor,
        guardrails=controller
    )
    
    print("✅ System Initialized. Running Loop...")
    
    # 4. Run Loop
    for i in range(45, 60):
        current_time = dates[i]
        def provider(s): return df.iloc[:i+1]
        
        for _ in test_coins:
            multi_engine.tick(current_time, provider)
            
    # 5. Check Results
    state = executor.get_balance()
    pos = state['positions']
    
    print("\n--- Results ---")
    print(f"Open Positions in: {list(pos.keys())}")
    
    success = True
    
    # G_OK should be IN
    # NOTE: It might have closed (TP) if price rose too much.
    # Check trade history counts instead for robustness.
    
    hist = executor.trade_history
    trades_ok = [t for t in hist if t['symbol'] == "G_OK"]
    trades_cold = [t for t in hist if t['symbol'] == "G_COLD"]
    trades_rej = [t for t in hist if t['symbol'] == "G_REJECTED"]
    
    if len(trades_ok) > 0:
        print("✅ G_OK: Traded (Correct).")
    else:
        print("❌ G_OK: No Trade (Failed).")
        success = False
        
    if len(trades_cold) == 0:
        print("✅ G_COLD: Blocked (Correct).")
    else:
        print(f"❌ G_COLD: Traded! (Failed) -> {trades_cold}")
        success = False
        
    if len(trades_rej) == 0:
        print("✅ G_REJECTED: Blocked (Correct).")
    else:
        print(f"❌ G_REJECTED: Traded! (Failed) -> {trades_rej}")
        success = False

    if success:
        print("\n🏆 MISSION ACCOMPLISHED: Intelligence Bridge Active.")
    else:
        print("\n⚠️ MISSION FAILED.")

if __name__ == "__main__":
    verify_fusion()
