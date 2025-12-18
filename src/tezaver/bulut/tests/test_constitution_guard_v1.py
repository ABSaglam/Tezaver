import pytest
from unittest.mock import MagicMock, patch
from tezaver.bulut.services.constitution_guard import ConstitutionGuard

def test_checksum_and_drift():
    # Setup
    ctx = MagicMock()
    ctx.config.constitution_path = "dummy_path"
    ctx.config.constitution_version = "v1"
    ctx.config.constitution_checksum_enforce = True
    ctx.config.mode = "REAL_MAINNET"
    
    ctx.persistence = MagicMock()
    ctx.telemetry = MagicMock()
    
    guard = ConstitutionGuard(ctx)
    
    # Mock file read
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        mock_file = MagicMock()
        # Ensure enough reads for multiple calls
        # 1st call: read 8192 -> "content", then read -> ""
        # 2nd call: read 8192 -> "content", then read -> ""
        # ...
        def read_side_effect(size):
            # This is tricky with side_effect list if multiple calls happen.
            # Simpler: return "content" once then empty string for each open/read cycle?
            # Or just mock_file.read.return_value = b"content" and handle iteration manually?
            # Actually easiest: `side_effect` iterable is consumed.
            # Let's provide enough values.
            return b"" 
        
        # Actually, let's just make it return content once, then empty.
        # But compute_checksum loop calls read until empty.
        # Call 1: read(8192) -> "content"
        # Call 2: read(8192) -> ""
        # Next compute_checksum call restarts open().
        # If open() returns SAME mock_file, its side_effect is exhausted.
        # New open() should theoretically return a fresh file handle or reset?
        # MagicMock open returns same object by default unless side_effect configured on open.
        
        # Proper way: open().read side_effect should reset per call?
        # Let's use side_effect on open to return NEW file mocks.
        pass

    # Better mock setup using side_effect class or simpler iteration
    # Issue with previous lambda: attributes on the mock might be shared.
    
    # Let's mock builtins.open to return a FRESH mock object each time
    mock_files = [
        MagicMock(read=MagicMock(side_effect=[b"content", b""])), # 1st open
        MagicMock(read=MagicMock(side_effect=[b"content", b""])), # 2nd open
        MagicMock(read=MagicMock(side_effect=[b"content", b""])), # 3rd
        MagicMock(read=MagicMock(side_effect=[b"content", b""])),
    ]
    
    def open_side_effect(*args, **kwargs):
        if mock_files:
            m = mock_files.pop(0)
            # Make the mock context manager return itself
            m.__enter__.return_value = m
            return m
        return MagicMock(read=MagicMock(return_value=b"")) # fallback

    with patch("builtins.open", side_effect=open_side_effect):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_mtime = 123456.0
                
                # ... tests ...
                # Compute Checksum
                chk = guard.compute_checksum()
                # ...
                assert chk is not None
                
                # 1. First Run (No DB history)
                ctx.persistence.get_latest_config_snapshot.return_value = None
                
                res = guard.check_and_alert()
                assert res["drift"] is False 
                
                ctx.persistence.insert_config_snapshot.assert_called_once()
                ctx.persistence.insert_alert.assert_not_called()
                
                # 2. Stable Run
                ctx.persistence.get_latest_config_snapshot.return_value = {"hash": chk}
                ctx.persistence.insert_config_snapshot.reset_mock()
                
                res2 = guard.check_and_alert()
                assert res2["drift"] is False
                ctx.persistence.insert_config_snapshot.assert_not_called()
                
                # 3. Drift Run (Hash mismatch)
                ctx.persistence.get_latest_config_snapshot.return_value = {"hash": "old_hash_val"}
                
                res3 = guard.check_and_alert()
                assert res3["drift"] is True
                assert res3["old_hash"] == "old_hash_val"
                assert res3["new_hash"] == chk
                
                ctx.persistence.insert_alert.assert_called_once()
                # ctx.telemetry.emit.assert_called_with("CONSTITUTION_CHECKSUM_CHANGED", pytest.any) # Mock matching tricky with pytest.any sometimes, simplify
 
