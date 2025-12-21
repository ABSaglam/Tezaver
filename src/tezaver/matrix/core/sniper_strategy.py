from typing import List, Optional, Dict, Any
from tezaver.matrix.core.bars import Bar
from tezaver.matrix.core.state import RunState
from tezaver.matrix.core.order_lifecycle import Order, OrderStatus
from tezaver.matrix.core.candidate_v1 import PayloadV1

class SniperStrategy:
    """
    MXI-1100: Real Sniper Strategy logic.
    TR: Gerçek Sniper strateji mantığı. Aday paketindeki hikayeleri (stories) bar bar takip eder.
    """
    def __init__(self, payload: PayloadV1):
        self.payload = payload
        self.active_story_idx = 0
        self.orders = []

    def decide(self, bar: Bar, state: RunState) -> Optional[Order]:
        """
        Produces an order if a story trigger is met.
        """
        # 1. Check if we are in a position
        if state.position.qty > 0:
            # Simple Exit Logic: Stop Loss or Take Profit (stubbed for now or based on story)
            # In a real sniper, we'd follow the story's exit levels.
            # Let's check for stop loss
            # (In this sprint, we focus on entry and basic flow)
            return None

        # 2. Check stories
        for story in self.payload.stories:
            # Entry condition: bar.ts matches story event_time
            # Story event_time is likely ISO string, need to convert or compare
            event_time_str = story.entry.get("event_time_utc")
            if not event_time_str: continue
            
            from datetime import datetime
            try:
                event_ts = int(datetime.fromisoformat(event_time_str.replace('Z', '+00:00')).timestamp() * 1000)
            except:
                continue

            # If current bar is exactly the trigger window
            if bar.ts == event_ts:
                # ENTRY!
                order_id = f"SO_{story.story_id}_{bar.ts}"
                order = Order(
                    order_id=order_id,
                    symbol=story.symbol,
                    side="BUY",
                    qty=1.0, # Fixed qty for now
                    limit_price=bar.close,
                    created_ts=bar.ts
                )
                return order
                
        return None
