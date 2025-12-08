import sys
import os
from datetime import datetime
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tezaver.engine.interfaces import MarketSignal, AccountState, TradeDecision, ExecutionReport
from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer
from tezaver.engine.strategists.rally_strategist import RallyStrategist
from tezaver.engine.matrix_executor import MatrixExecutor
from tezaver.engine.unified_engine import UnifiedEngine

def verify_system():
    print(">>> M25 Matrix System Verification Initiated <<<")
    
    # 1. Instantiate Trinity
    try:
        analyzer = RallyAnalyzer(rally_threshold=0.01) # Low threshold for test
        strategist = RallyStrategist()
        executor = MatrixExecutor(initial_balance_usdt=10000)
        engine = UnifiedEngine(analyzer, strategist, executor)
        print("✅ Trinity Instantiated Successfully.")
    except Exception as e:
        print(f"❌ Instantiation Failed: {e}")
        return

    # 2. Mock Data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    # Generate prices: Start flat, then RALLY
    prices = [100.0] * 50 + [100.0 * (1.05**i) for i in range(50)] # Explosion
    
    df = pd.DataFrame({
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * 100
    }, index=dates)
    
    print(f"✅ Mock Data Created (100 bars).")
    
    # 3. Run Loop
    symbol = "BTCUSDT"
    trade_count = 0
    
    print("\n--- Starting Simulation Loop ---")
    for i in range(45, 65): # Run just the breakout part
        window = df.iloc[:i]
        
        try:
            result = engine.tick(symbol, "1h", window)
            
            # Debug
            # print(f"Tick {i}: Signals={len(result['signals'])} Dec={result['decision'] is not None}")
            
            # Check Signals
            if result['signals']:
                sig = result['signals'][0]
                print(f"[{window.index[-1]}] SIGNAL: {sig['signal_type']} Score: {sig['score']:.2f}")
            else:
                pass # No signal
                
            # Check Decision
            if result['decision']:
                dec = result['decision']
                print(f"[{window.index[-1]}] DECISION: {dec['action']} Size: {dec['quantity']:.4f}")
                
            # Check Execution
            if result['execution']:
                exe = result['execution']
                print(f"[{window.index[-1]}] EXECUTION: {exe['status']} {exe['action']} Price: {exe['filled_price']}")
                if exe['success']:
                    trade_count += 1
                    
        except Exception as e:
            print(f"❌ CRITICAL ERROR at index {i}: {e}")
            import traceback
            traceback.print_exc()
            return
            
    print("\n--- Summary ---")
    if trade_count > 0:
        print(f"✅ Trades Executed: {trade_count}")
        print("✅ System Flow Verified.")
    else:
        print("⚠️ No trades executed. Check thresholds?")
        
    # Check Balance Structure
    state = executor.get_balance()
    if 'equity' in state and 'positions' in state:
        print(f"✅ AccountState Structure Verified. Equity: {state['equity']:.2f}")
    else:
        print(f"❌ AccountState Structure Invalid: {state.keys()}")

if __name__ == "__main__":
    verify_system()
