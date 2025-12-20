from tezaver.matrix.core.story_compiler import compile_story

def test_compile_15m_to_1h():
    source = {
        "symbol": "BTC", "timeframe": "15m", "build_ts": "2024", "bundle_version": "v1",
        "story": {
            "phases": [
                {"name": "P1", "start_bar": 0, "end_bar": 3},   # 0-3 -> 0-0
                {"name": "P1", "start_bar": 4, "end_bar": 7}    # 4-7 -> 1-1
                # Should NOT merge because of gap? 
                # 0 // 4 = 0, 3 // 4 = 0.
                # 4 // 4 = 1, 7 // 4 = 1.
                # End of first is 0. Start of second is 1. Adjacent. 0+1=1. 
                # Logic: start <= last_end + 1. 1 <= 0 + 1. True. Merge!
            ],
            "anchors": {"entry_bar": 8, "invalidation_bar": 4} # 8->2, 4->1
        }
    }
    
    compiled = compile_story(source, "1h")
    
    # Verify Timeframe
    assert compiled["timeframe"] == "1h"
    
    # Verify Phases Merged
    phases = compiled["story"]["phases"]
    assert len(phases) == 1
    assert phases[0]["name"] == "P1"
    assert phases[0]["start_bar"] == 0
    assert phases[0]["end_bar"] == 1
    
    # Verify Anchors
    anchors = compiled["story"]["anchors"]
    assert anchors["entry_bar"] == 2
    assert anchors["invalidation_bar"] == 1

def test_compile_15m_to_4h():
    source = {
        "symbol": "BTC", "timeframe": "15m", 
        "story": { "phases": [], "anchors": {"entry_bar": 32} } # 32 // 16 = 2
    }
    compiled = compile_story(source, "4h")
    assert compiled["story"]["anchors"]["entry_bar"] == 2
