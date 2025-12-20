from tezaver.matrix.core.story_render import render_story_html

def test_render_simple():
    bundle = {
        "symbol": "BTC", "timeframe": "15m", "build_ts": "2024", "bundle_version": "v1",
        "story": {
            "phases": [
                {"name": "P1", "start_bar": 0, "end_bar": 10},
                {"name": "P2", "start_bar": 11, "end_bar": 20}
            ],
            "anchors": {"entry_bar": 15, "invalidation_bar": 5},
            "tags": ["TEST"]
        }
    }
    
    html = render_story_html(bundle)
    assert "Story: BTC" in html
    assert "Range: 0 -> 20" in html
    assert "P1" in html
    assert "########" in html # Check ascii bar existence roughly

def test_render_signatures():
    bundle = {
        "symbol": "BTC", "timeframe": "15m", "build_ts": "2024", "bundle_version": "v1",
        "story": {
            "phases": [],
            "anchors": {"entry_bar":0, "invalidation_bar":0},
            "signatures": {"rsi": {"min":30, "max":70, "mean":50}}
        }
    }
    html = render_story_html(bundle)
    assert "Signatures:" in html
    assert "PASS" in html
