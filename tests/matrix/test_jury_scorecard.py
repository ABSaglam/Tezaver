from tezaver.matrix.core.jury import compute_scorecard
import os
import json

def test_jury_scorecard_counts(tmp_path):
    # Setup
    run_id = "test_run_1"
    run_dir = tmp_path / "runs" / run_id
    os.makedirs(run_dir)
    
    # 3 BAR events, 2 DECISION events, 1 BLOCK event
    events = [
        {"event_type": "BAR"},
        {"event_type": "BAR"},
        {"event_type": "BAR"},
        {"event_type": "DECISION"},
        {"event_type": "DECISION"},
        {"event_type": "BLOCK"},
        {"event_type": "OTHER"}
    ]
    with open(run_dir / "events.ndjson", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
            
    # Compute
    card = compute_scorecard(str(tmp_path), run_id)
    
    assert card["run_id"] == run_id
    assert card["bars_count"] == 3
    assert card["decisions_count"] == 2
    assert card["blocks_count"] == 1
    assert card["incidents_count"] == 0
