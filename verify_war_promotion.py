
from tezaver.matrix.sniper.certification_registry import CertificationRegistry, STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED
from tezaver.matrix.sniper.promotion_manager import PromotionManager
from tezaver.matrix.pool.portfolio_models_v2 import PortfolioStateV2, PortfolioPositionV2, PortfolioTotalsV2

def test_war_promotion():
    print("--- Testing War Promotion (Sim WinRate) ---")
    
    # Setup
    reg = CertificationRegistry()
    pm = PromotionManager(cert_registry=reg)
    
    bundle_id = "test_bundle_war_01"
    
    # Force initial state to SNIPER_PASSED (War Ready)
    reg.certify_sniper_pass(bundle_id, "Manual Setup")
    print(f"Initial Stage: {reg.get_bundle_stage(bundle_id)}")
    
    # Create Mock Portfolio with 3 trades
    # 2 Wins, 1 Loss. WinRate = 66%. Target for Diamond is 70%, required 63%.
    # Should PASS.
    
    positions = [
        PortfolioPositionV2(
            pos_id="p1", symbol="ADAUSDT", timeframe="15m", bundle_id=bundle_id, status="CLOSED",
            opened_ts_iso="", closed_ts_iso="", avg_entry=1, qty=1, notional_entry=100,
            fees_paid=0, slippage_paid=0, realized_pnl=10.0, unrealized_pnl=0, # WIN
            last_mark_price=0, last_mark_ts_iso=""
        ),
        PortfolioPositionV2(
            pos_id="p2", symbol="ADAUSDT", timeframe="15m", bundle_id=bundle_id, status="CLOSED",
            opened_ts_iso="", closed_ts_iso="", avg_entry=1, qty=1, notional_entry=100,
            fees_paid=0, slippage_paid=0, realized_pnl=10.0, unrealized_pnl=0, # WIN
            last_mark_price=0, last_mark_ts_iso=""
        ),
        PortfolioPositionV2(
            pos_id="p3", symbol="ADAUSDT", timeframe="15m", bundle_id=bundle_id, status="CLOSED",
            opened_ts_iso="", closed_ts_iso="", avg_entry=1, qty=1, notional_entry=100,
            fees_paid=0, slippage_paid=0, realized_pnl=-5.0, unrealized_pnl=0, # LOSS
            last_mark_price=0, last_mark_ts_iso=""
        )
    ]
    
    mock_state = PortfolioStateV2(
        version="v2", updated_ts_iso="", positions=positions, totals=PortfolioTotalsV2(0,0,0,0,0,0)
    )
    
    print("\nRunning Promotion Manager update...")
    pm.update_promotions_from_portfolio(mock_state)
    
    new_stage = reg.get_bundle_stage(bundle_id)
    print(f"New Stage: {new_stage}")
    
    assert new_stage == STAGE_LIVE_CERTIFIED
    print("\n✅ War Promotion Verified!")

if __name__ == "__main__":
    test_war_promotion()
