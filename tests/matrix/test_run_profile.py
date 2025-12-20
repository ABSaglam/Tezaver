import pytest
from tezaver.matrix.core.run_profile import require_profile

def test_valid_profiles():
    require_profile("SNIPER")
    require_profile("WAR")
    require_profile("LIVE")

def test_invalid_profile():
    with pytest.raises(ValueError):
        require_profile("UNKNOWN")
    with pytest.raises(ValueError):
        require_profile("")
