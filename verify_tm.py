
import json
from tezaver.matrix.backtest.time_machine_v1 import MatrixTimeMachine

# Mock Manifest
manifest = {
    "bundle_version": "approved_rally_bundle_v1",
    "bundle_id": "TEST_BUNDLE",
    "symbol": "BTCUSDT",
    "timeframe": "15m",
    "event_id": "EVT_TEST",
    "event_time_iso": "2024-01-01T00:00:00Z",
    "approved": {"entry_bar_offset": 1, "entry_ts": "2024-01-01T00:15:00Z"},
    "qc": {"verdict": "PASS", "score": 90},
    "trigger_spec_v1": {"type": "RSI_CROSS", "param": 14, "threshold": 30},
    "policy_spec_v1": {"exit_policy": "TP_SL", "notional": 100}
}

try:
    tm = MatrixTimeMachine("BTCUSDT", "15m", start_balance=1000.0)
    # Run slightly shorter range to be fast
    # 2024 start = 1704067200000
    res = tm.run(manifest, start_ts=1704067200000, end_ts=1706659200000) # 1 month
    print("Result Keys:", res.keys())
    if "error" in res:
        print("Error:", res["error"])
    else:
        print("Trades:", len(res["trades"]))
        print("Final Equity:", res["final_equity"])
        print("Final Balance:", res["final_balance"])

except Exception as e:
    import traceback
    traceback.print_exc()
