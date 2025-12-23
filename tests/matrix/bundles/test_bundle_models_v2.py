import pytest
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1

# Helper to create a valid base V1 dict
def create_base_manifest_dict():
    return {
        "bundle_version": "approved_rally_bundle_v1",
        "bundle_id": "bundle_123",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "event_id": "event_123",
        "event_time_iso": "2023-01-01T00:00:00Z",
        "approved": {
            "entry_bar_offset": 10,
            "entry_ts": "2023-01-01T00:00:00Z"
        },
        "qc": {
            "verdict": "PASS",
            "score": 95
        }
    }

def test_v1_compatibility():
    """Ensure V1 manifest logic still works (no new fields)."""
    data = create_base_manifest_dict()
    manifest = ApprovedRallyBundleManifestV1.from_dict(data)
    
    assert manifest.bundle_id == "bundle_123"
    assert manifest.trigger_spec_v1 is None
    assert manifest.policy_spec_v1 is None

def test_v2_valid():
    """Ensure V2 fields are parsed correctly."""
    data = create_base_manifest_dict()
    data["trigger_spec_v1"] = {"type": "CLOSED_BAR_SIGNAL", "params": {"bar_count": 1}}
    data["policy_spec_v1"] = {"exit_policy": "ATR", "params": {"mult": 2.0}}
    
    manifest = ApprovedRallyBundleManifestV1.from_dict(data)
    
    assert manifest.trigger_spec_v1 is not None
    assert manifest.trigger_spec_v1["type"] == "CLOSED_BAR_SIGNAL"
    assert manifest.trigger_spec_v1["params"]["bar_count"] == 1
    
    assert manifest.policy_spec_v1 is not None
    assert manifest.policy_spec_v1["exit_policy"] == "ATR"
    assert manifest.policy_spec_v1["params"]["mult"] == 2.0

def test_v2_invalid_trigger_type():
    """Ensure missing type in trigger_spec raises ValueError."""
    data = create_base_manifest_dict()
    data["trigger_spec_v1"] = {"params": {}} # Missing 'type'
    
    with pytest.raises(ValueError, match="trigger_spec_v1 missing 'type'"):
        ApprovedRallyBundleManifestV1.from_dict(data)

def test_v2_invalid_trigger_not_dict():
    """Ensure trigger_spec must be a dict."""
    data = create_base_manifest_dict()
    data["trigger_spec_v1"] = "invalid_string"
    
    with pytest.raises(ValueError, match="trigger_spec_v1 must be a dict"):
        ApprovedRallyBundleManifestV1.from_dict(data)

def test_v2_invalid_policy_exit_policy():
    """Ensure missing exit_policy in policy_spec raises ValueError."""
    data = create_base_manifest_dict()
    data["policy_spec_v1"] = {"params": {}} # Missing 'exit_policy'
    
    with pytest.raises(ValueError, match="policy_spec_v1 missing 'exit_policy'"):
        ApprovedRallyBundleManifestV1.from_dict(data)

def test_v2_invalid_policy_not_dict():
    """Ensure policy_spec must be a dict."""
    data = create_base_manifest_dict()
    data["policy_spec_v1"] = 123
    
    with pytest.raises(ValueError, match="policy_spec_v1 must be a dict"):
        ApprovedRallyBundleManifestV1.from_dict(data)
