import pandas as pd
from datetime import datetime
from tezaver.mac.export.story_builder import RallyStoryBuilder

def test_pre_pattern_fill():
    config = {"sl_atr_k": 1.5}
    builder = RallyStoryBuilder(config)
    
    event_row = pd.Series({
        "event_time": datetime(2023, 10, 1, 12, 0),
        "event_tf": "15m",
        "symbol": "BTCUSDT",
        "bars_total": 100,
        "bars_to_peak": 12,
        "rsi_15m": 45.0,
        "macd_phase_15m": "KOSU",
        "volume_rel_15m": 2.5,
        "future_max_gain_pct": 0.05,
        "atr_pct_15m": 1.0,
        "quality_score": 85,
        "rally_shape": "V",
        "trend_efficiency": 0.9,
        "narrative_tr": "Deneme anlatı"
    })
    
    # Mock data ports
    # history_df needs 'timestamp' and 'datetime'
    evt_time = datetime(2023, 10, 1, 12, 0)
    ts = int(evt_time.timestamp()*1000)
    history_df = pd.DataFrame([{"timestamp": ts, "close": 27000.0}])
    history_df['datetime'] = pd.to_datetime(history_df['timestamp'], unit='ms')
    
    patterns_df = pd.DataFrame(columns=["timestamp", "trigger"])
    levels = [{"type": "support", "level_price": 26500.0, "strength_score": 10}]
    regime = {"regime": "TREND", "trendiness_score": 80, "chop_score": 10}
    shock = {"shock_freq": 0.02}
    
    story = builder.build_story(
        symbol="BTCUSDT",
        event_row=event_row,
        history_df=history_df,
        patterns_df=patterns_df,
        levels=levels,
        regime=regime,
        shock=shock,
        pattern_stats=[],
        families=[]
    )
    
    print("--- RallyStory Pre-Pattern Verification ---")
    pp = story.get("pre_pattern")
    if not pp:
        print("FAIL: pre_pattern is missing!")
        return

    entry_p = story["entry"]["entry_price"]
    print(f"Calculated Entry Price: {entry_p}")
    print(f"Nearest Support: {story['entry']['levels']['nearest_support']}")
    
    print(f"Rhythm Summary: {pp['rhythm']['summary_tr']}")
    print(f"Spirit Summary: {pp['spirit']['summary_tr']}")
    print(f"Thesis: {pp['meaning']['thesis_tr']}")
    print(f"Invalidation: {pp['meaning']['invalidation_tr']}")
    
    # Check deterministic values
    if "100 barlık bir pencerede" in pp['rhythm']['summary_tr']:
         print("SUCCESS: Rhythm template matches.")
    if "TREND rejiminde" in pp['spirit']['summary_tr']:
         print("SUCCESS: Spirit template matches.")
    if "26500.0" in pp['meaning']['invalidation_tr'] or "26500" in pp['meaning']['invalidation_tr']:
         print("SUCCESS: Invalidation template matches support level.")

if __name__ == "__main__":
    test_pre_pattern_fill()
