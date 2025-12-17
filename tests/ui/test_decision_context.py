
import tests.mock_env
import unittest
from datetime import datetime, timedelta, timezone
from tezaver.ui.trade_replay_data import build_decision_context, build_trade_timeline, TimelineRow, Trade

def mk_event(ts: datetime, etype: str, **kwargs) -> dict:
    e = {
        "ts": ts.isoformat(),
        "event_type": etype,
    }
    e.update(kwargs)
    return e

class TestDecisionContext(unittest.TestCase):
    def test_decision_context_summary_populates_from_events(self):
        base = datetime.now(timezone.utc)
        trade_open = base
        
        events = [
            mk_event(base - timedelta(minutes=5), "PREFLIGHT_EVAL", decision=True),
            mk_event(base - timedelta(minutes=4), "CARD_GATE_EVAL", decision=True, gate="MyCard"),
            mk_event(base - timedelta(minutes=3), "RISK_LIMIT_CHECK", decision=True),
            mk_event(base - timedelta(minutes=2), "HTF_PERMISSION_EVAL", decision="ALLOW"),
            mk_event(base - timedelta(minutes=1), "STRATEGY_SIGNAL", signal="OPEN_LONG", reason="RSI_DIVERGENCE"),
            mk_event(base + timedelta(minutes=10), "POSITION_CLOSE", reason="TP_HIT"), 
        ]
        
        trade = Trade(
            trade_id="t1", symbol="BTCUSDT", timeframe="15m",
            open_ts=trade_open.isoformat(), close_ts=(base + timedelta(minutes=10)).isoformat(),
            net_pnl=0.0, side="LONG", open_px=100.0, close_px=101.0, qty=1.0,
            close_reason="TP_HIT"
        )
        
        ctx = build_decision_context(events, trade)
        
        self.assertEqual(ctx["summary"], "Sig: OPEN_LONG (RSI_DIVERGENCE) | HTF: ALLOW | Risk: PASS")

    def test_timeline_filters_and_caps_rows(self):
        base = datetime.now(timezone.utc)
        
        # Generate 50 mixed events
        events = []
        for i in range(50):
            etype = "ROUTER_TICK" if i % 2 == 0 else "RISK_LIMIT_CHECK" 
            events.append(mk_event(base + timedelta(minutes=i), etype, decision=True))
            
        events.append(mk_event(base, "STRATEGY_SIGNAL", signal="OPEN_LONG"))
        events.append(mk_event(base + timedelta(hours=1), "ORDER_LIFECYCLE_DONE", action="SELL"))
        
        trade = Trade(
            trade_id="t1", symbol="BTCUSDT", timeframe="15m",
            open_ts=base.isoformat(), close_ts=(base + timedelta(hours=2)).isoformat(),
            net_pnl=0.0, side="LONG", open_px=100.0, close_px=101.0, qty=1.0,
            close_reason="TP_HIT"
        )
        
        timeline = build_trade_timeline(events, trade)
        
        # Validation
        self.assertLessEqual(len(timeline), 30)
        
        for row in timeline:
            self.assertNotEqual(row.event_type, "ROUTER_TICK")

if __name__ == '__main__':
    unittest.main()
