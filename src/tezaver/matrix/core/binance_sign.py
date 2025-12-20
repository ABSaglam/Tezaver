import hmac
import hashlib
import urllib.parse
from typing import Dict, Any

def build_query_string(params: Dict[str, Any]) -> str:
    """
    Constructs a canonical query string from a dictionary.
    Keys are sorted alphabetically.
    Values are url-encoded.
    """
    if not params:
        return ""
    
    # Sort by key
    sorted_keys = sorted(params.keys())
    parts = []
    for k in sorted_keys:
        v = params[k]
        encoded_k = urllib.parse.quote(str(k))
        encoded_v = urllib.parse.quote(str(v))
        parts.append(f"{encoded_k}={encoded_v}")
        
    return "&".join(parts)

def sign_request(params: Dict[str, Any], secret: str) -> str:
    """
    Generates HMAC SHA256 signature for the given parameters using the secret.
    The parameters are first converted to a query string.
    Returns the signature as a hex string.
    """
    query_string = build_query_string(params)
    signature = hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature
