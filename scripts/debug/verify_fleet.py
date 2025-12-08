import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tezaver.engine.matrix_executor import MatrixExecutor
from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer
from tezaver.engine.strategists.rally_strategist import RallyStrategist
from tezaver.matrix.multi_symbol_engine import MultiSymbolEngine
from tezaver.matrix.guardrail import GuardrailController, SymbolGuardrailData

def verify_fleet():
    print(">>> M25.3 Fleet Verification Initiated <<<")
    
    symbols = ["BTC", "ETH"]
    
    # 1. Mock Data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    # BTC Explodes
    prices_btc = [100.0] * 50 + [100.0 * (1.05**i) for i in range(50)]
    # ETH Crashes (Should trigger nothing or SELL)
    prices_eth = [2000.0] * 100
    
    data_map = {
        "BTC": pd.DataFrame({"close": prices_btc, "high": prices_btc, "low": prices_btc}, index=dates),
        "ETH": pd.DataFrame({"close": prices_eth, "high": prices_eth, "low": prices_eth}, index=dates)
    }
    
    # 2. Setup Fleet
    guardrail_data = {
        "BTC": SymbolGuardrailData(promotion_status="APPROVED", radar_state="HOT"),
        "ETH": SymbolGuardrailData(promotion_status="APPROVED", radar_state="COLD") # COLD should block LONG? No, controller logic block COLD.
    }
    controller = GuardrailController(
        global_limits={"max_open_positions": 5},
        symbol_data=guardrail_data
    )
    
    executor = MatrixExecutor(initial_balance_usdt=50000)
    
    # Use Factory Lambdas
    multi_engine = MultiSymbolEngine(
        symbols=symbols,
        analyzer_factory=lambda s: RallyAnalyzer(rally_threshold=0.01), # Sensitivity 1%
        strategist_factory=lambda s: RallyStrategist(),
        executor=executor,
        guardrails=controller
    )
    
    print("✅ Fleet Initialized.")
    
    # 3. Simulate Loop
    
    for i in range(45, 60): # Breakout Zone
        current_time = dates[i]
        
        def provider(sym):
            return data_map[sym].iloc[:i+1]
            
        # Tick all symbols
        for _ in symbols:
            multi_engine.tick(current_time, provider)
            
    # 4. Check Results
    state = executor.get_balance()
    positions = state['positions']
    
    print("\n--- Fleet Status ---")
    print(f"Equity: {state['equity']:.2f}")
    print(f"Positions: {list(positions.keys())}")
    
    if "BTC" in positions:
        print("✅ BTC Position Opened (Correct).")
    else:
        print("❌ BTC Position Missing (Failed).")
        
    if "ETH" in positions:
        print("❌ ETH Position Opened (Unexpected - Price was flat).")
    else:
        print("✅ ETH Position Flat (Correct).")

if __name__ == "__main__":
    verify_fleet()
