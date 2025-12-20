import pytest
from tezaver.matrix.core.fingerprint import fingerprint_ts_list, fingerprint_file

def test_fingerprint_ts_determinism():
    ts = [100, 200, 300]
    fp1 = fingerprint_ts_list(ts)
    fp2 = fingerprint_ts_list(ts)
    assert fp1 == fp2
    
def test_fingerprint_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")
    
    fp1 = fingerprint_file(str(f))
    fp2 = fingerprint_file(str(f))
    assert fp1 == fp2
    # echo -n "hello world" | shasum -a 256
    # b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
    assert fp1 == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
