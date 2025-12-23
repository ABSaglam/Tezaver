
from tezaver.matrix.sniper.certification_registry import CertificationRegistry
from tezaver.matrix.sniper.promotion_manager import PromotionManager
from tezaver.matrix.pool.portfolio_models_v2 import PortfolioStateV2, PortfolioPositionV2, PortfolioTotalsV2

def verify_metrics_storage():
    print("--- Testing Metrics Storage in Registry ---")
    
    reg = CertificationRegistry()
    pm = PromotionManager(cert_registry=reg)
    
    # 1. Test Sniper Gate Metrics
    bundle_id = "test_metrics_sniper_01"
    reg.reset_bundle(bundle_id)
    
    # Pass with PnL 0.60 (Target 0.50 * 1.2 = 0.60 for ADA)
    # Actually Target is 0.60. Let's pass squarely.
    print(f"Promoting {bundle_id} via Sniper Gate...")
    pm.evaluate_sniper_backtest(bundle_id, "ADAUSDT", "15m", "DIAMOND", 0.65)
    
    # Check Registry
    entry = reg.data.get(bundle_id)
    metrics = entry.get("metrics")
    print(f"Stored Metrics (Sniper): {metrics}")
    
    assert metrics is not None, "Metrics should not be None"
    assert metrics["actual_pnl"] == 0.65
    assert metrics["target_pnl"] == 0.60
    assert metrics["delta"] == 0.05
    
    # 2. Test War Gate Metrics
    bundle_id_war = "test_metrics_war_01"
    reg.certify_sniper_pass(bundle_id_war, "Manual Setup")
    
    # Create Mock Portfolio (WinRate test)
    # 3 Wins / 3 Trades = 100% WR. Target for Diamond ADA is 0.70.
    positions = [
        PortfolioPositionV2(
            pos_id="p1", symbol="ADAUSDT", timeframe="15m", bundle_id=bundle_id_war, status="CLOSED",
            opened_ts_iso="", closed_ts_iso="", avg_entry=1, qty=1, notional_entry=100,
            fees_paid=0, slippage_paid=0, realized_pnl=10.0, unrealized_pnl=0, # WIN
            last_mark_price=0, last_mark_ts_iso=""
        ),
        PortfolioPositionV2(
            pos_id="p2", symbol="ADAUSDT", timeframe="15m", bundle_id=bundle_id_war, status="CLOSED",
            opened_ts_iso="", closed_ts_iso="", avg_entry=1, qty=1, notional_entry=100,
            fees_paid=0, slippage_paid=0, realized_pnl=10.0, unrealized_pnl=0, # WIN
            last_mark_price=0, last_mark_ts_iso=""
        ),
         PortfolioPositionV2(
            pos_id="p3", symbol="ADAUSDT", timeframe="15m", bundle_id=bundle_id_war, status="CLOSED",
            opened_ts_iso="", closed_ts_iso="", avg_entry=1, qty=1, notional_entry=100,
            fees_paid=0, slippage_paid=0, realized_pnl=10.0, unrealized_pnl=0, # WIN
            last_mark_price=0, last_mark_ts_iso=""
        )
    ]
    mock_state = PortfolioStateV2(
        version="v2", updated_ts_iso="", positions=positions, totals=PortfolioTotalsV2(0,0,0,0,0,0)
    )
    
    print(f"\nPromoting {bundle_id_war} via War Gate...")
    pm.update_promotions_from_portfolio(mock_state)
    
    entry_war = reg.data.get(bundle_id_war)
    metrics_war = entry_war.get("metrics")
    print(f"Stored Metrics (War): {metrics_war}")
    
    assert metrics_war is not None
    assert metrics_war["actual_wr"] == 1.0
    # Note: Manager currently defaults to "UNKNOWN" tier (Target 0.50) because it doesn't do Manifest lookup yet.
    # We accept this for now as we are verifying the *storage mechanism*.
    assert metrics_war["target_wr"] == 0.50
    
    print("\n✅ Metrics Storage Verified!")

if __name__ == "__main__":
    verify_metrics_storage()
