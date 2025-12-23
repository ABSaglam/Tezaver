
from tezaver.matrix.sniper.certification_registry import CertificationRegistry, STAGE_CANDIDATE, STAGE_SNIPER_PASSED
from tezaver.matrix.sniper.promotion_manager import PromotionManager
from tezaver.matrix.sniper.benchmark_service import BenchmarkService

def test_sniper_gate():
    print("--- Testing Sniper Gate (Backtest PnL) ---")
    
    # Setup
    reg = CertificationRegistry()
    pm = PromotionManager(cert_registry=reg)
    
    bundle_id = "test_bundle_sniper_01"
    reg.reset_bundle(bundle_id) # Ensure candidate
    
    print(f"Initial Stage: {reg.get_bundle_stage(bundle_id)}")
    
    # 1. Fail Case: PnL below benchmark
    # Diamond benchmark PnL is 0.50 (50%). Let's try 0.20 (20%)
    print("\n1. Testing FAIL case (PnL=20%, Target=50%)...")
    is_passed = pm.evaluate_sniper_backtest(bundle_id, "ADAUSDT", "15m", "DIAMOND", 0.20)
    print(f"Passed: {is_passed}")
    print(f"Stage: {reg.get_bundle_stage(bundle_id)}")
    
    # 2. Pass Case: PnL meets benchmark (within 10% tolerance)
    # Diamond Target 0.50 * ADA Multiplier 1.2 = 0.60
    # Tolerance 10% -> Threshold 0.54
    # Let's try 0.55
    print("\n2. Testing PASS case (PnL=55%, Target=60% due to Multiplier)...")
    is_passed = pm.evaluate_sniper_backtest(bundle_id, "ADAUSDT", "15m", "DIAMOND", 0.55)
    print(f"Passed: {is_passed}")
    print(f"Stage: {reg.get_bundle_stage(bundle_id)}")
    
    assert reg.get_bundle_stage(bundle_id) == STAGE_SNIPER_PASSED
    print("\n✅ Sniper Gate Verified!")

if __name__ == "__main__":
    test_sniper_gate()
