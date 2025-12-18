# Tezaver Bulut - Entry Sizing v1 Tests
import sys
from unittest.mock import MagicMock

# Mock fastapi before imports if missing
try:
    import fastapi
except ImportError:
    m = MagicMock()
    m.HTTPException = Exception
    sys.modules["fastapi"] = m
try:
    import pydantic
except ImportError:
    m2 = MagicMock()
    m2.BaseModel = object
    sys.modules["pydantic"] = m2

import pytest
from pathlib import Path
import json
import shutil
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.services.entry_sizing_loader import EntrySizingLoader
from tezaver.bulut.services.entry_sizing_resolver import EntrySizingResolver, SizingResult
from tezaver.bulut.schemas.entry_sizing_profile_v1 import (
    EntrySizingProfileV1, EntrySizingRuleV1, EntrySizingScopeV1, EntrySizingSafetyV1
)

@pytest.fixture
def mock_rules_dir(tmp_path):
    d = tmp_path / "bulut_rules" / "entry_sizing_profiles"
    d.mkdir(parents=True)
    return d.parent

@pytest.fixture
def ctx(mock_rules_dir):
    config = BulutConfig()
    # Bypass frozen check for test patching
    object.__setattr__(config, "max_cell_notional_usdt", 100.0)
    object.__setattr__(config, "max_open_positions", 5)
    
    ctx = BulutContext(config)
    
    # Init Loader with mock path
    ctx._entry_sizing_loader = EntrySizingLoader(mock_rules_dir)
    ctx._entry_sizing_resolver = EntrySizingResolver(ctx, ctx.entry_sizing_loader)
    
    return ctx

def create_profile(loader, pid, priority, type, val, scope_sym=None, scope_pat=None):
    p = EntrySizingProfileV1(
        profile_id=pid,
        version="1.0",
        priority=priority,
        scope=EntrySizingScopeV1(symbol=scope_sym, pattern_id=scope_pat),
        rule=EntrySizingRuleV1(
            type=type,
            fixed_notional_usdt=val if type=="fixed_notional" else 0.0,
            pct=val if type=="pct_of_cap" else 0.0,
            cap_ref="MAX_CELL_NOTIONAL"
        ),
        safety=EntrySizingSafetyV1(min_notional_usdt=1.0)
    )
    # Save
    path = loader._profiles_dir / f"{pid}.json"
    loader._profiles_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(p.to_dict(), f)
    loader.load_all(force=True)

def test_loader_basic(ctx):
    loader = ctx.entry_sizing_loader
    assert len(loader.load_all()) == 0
    create_profile(loader, "p1", 10, "fixed_notional", 25.0, scope_sym="BTCUSDT")
    assert len(loader.load_all()) == 1
    assert loader.get_by_id("p1").rule.fixed_notional_usdt == 25.0

def test_resolver_global_fallback(ctx):
    # No profiles -> Should return notional based on default logic (100% of cell cap usually in v0, but resolver v1 defaults blocked? No, fallback.)
    # Wait, resolver fallback logic:
    # If no match -> fallback to defaults?
    # Resolver implementation:
    # default_notional = min(ctx.config.max_cell_notional_usdt, 100.0) -> Hardcoded in Decider previously.
    # New Resolver implementation: 
    # If no match found? It returns blocked?
    # Let's check implementation. It looked for matching profiles. If none, what happens?
    
    # In my implementation of `entry_sizing_resolver.py`:
    # "If candidates list is empty, fallback to config max cell"
    
    res = ctx.entry_sizing_resolver.resolve("BTCUSDT", "pat1")
    assert not res.blocked
    assert res.notional_usdt == 100.0 # Default fallback
    assert res.profile_id == "FALLBACK_LEGACY"

def test_resolver_precedence(ctx):
    # Setup
    # 1. Global (Pri 0) -> 20 USDT
    create_profile(ctx.entry_sizing_loader, "global", 0, "fixed_notional", 20.0)
    
    res = ctx.entry_sizing_resolver.resolve("BTCUSDT")
    assert res.notional_usdt == 20.0
    assert res.profile_id == "global"
    
    # 2. Symbol (Pri 10) -> 30 USDT
    create_profile(ctx.entry_sizing_loader, "sym_btc", 10, "fixed_notional", 30.0, scope_sym="BTCUSDT")
    
    res = ctx.entry_sizing_resolver.resolve("BTCUSDT")
    assert res.notional_usdt == 30.0
    assert res.profile_id == "sym_btc"
    
    res = ctx.entry_sizing_resolver.resolve("ETHUSDT") # Should hit global
    assert res.notional_usdt == 20.0
    
    # 3. Pattern (Pri 20) -> 40 USDT
    create_profile(ctx.entry_sizing_loader, "pat_bull_flag", 20, "fixed_notional", 40.0, scope_pat="bull_flag")
    
    res = ctx.entry_sizing_resolver.resolve("BTCUSDT", "bull_flag") # Pattern > Symbol? Wait, Pattern is generic.
    # Precedence Rule: Symbol+Pattern > Pattern > Symbol > Global
    # Let's check logic order in resolver.
    # 1. symbol + pattern matches
    # 2. pattern matches (generic)
    # 3. symbol matches
    # 4. global (no scope)
    
    # Here:
    # "sym_btc" is SCOPE: Symbol.
    # "pat_bull_flag" is SCOPE: Pattern.
    # If we have BOTH:
    # Which wins? Pattern or Symbol?
    # Spec: "Symbol+Pattern > Pattern > Symbol > Global"
    
    # Let's verify.
    res = ctx.entry_sizing_resolver.resolve("BTCUSDT", "bull_flag")
    # Matches: sym_btc (Symbol), pat_bull_flag (Pattern), global (Global).
    # Expected Order: Pattern (since it's more specific to behavior?) or Symbol (specific to asset?)
    # Implementation:
    # - Symbol+Pattern Matches
    # - Pattern Matches
    # - Symbol Matches
    # - Global Matches
    # So Pattern (generic) comes BEFORE Symbol?
    # Yes, typically Logic > Asset.
    
    assert res.notional_usdt == 40.0
    assert res.profile_id == "pat_bull_flag"
    
    # 4. Symbol + Pattern (Pri 100) -> 50 USDT
    create_profile(ctx.entry_sizing_loader, "btc_bull", 100, "fixed_notional", 50.0, scope_sym="BTCUSDT", scope_pat="bull_flag")
    
    res = ctx.entry_sizing_resolver.resolve("BTCUSDT", "bull_flag")
    assert res.notional_usdt == 50.0
    assert res.profile_id == "btc_bull"

def test_resolver_calculation_pct(ctx):
    # Cap is 100. Profile says 50% -> 50 USDT
    create_profile(ctx.entry_sizing_loader, "pct_50", 10, "pct_of_cap", 50.0, scope_sym="ETHUSDT")
    
    res = ctx.entry_sizing_resolver.resolve("ETHUSDT")
    assert res.notional_usdt == 50.0

def test_safety_clamping(ctx):
    # Min notional clamp
    p = EntrySizingProfileV1(
        profile_id="clamp_min", version="1", priority=10,
        scope=EntrySizingScopeV1(symbol="SOLUSDT"),
        rule=EntrySizingRuleV1(type="fixed_notional", fixed_notional_usdt=5.0), # Low
        safety=EntrySizingSafetyV1(min_notional_usdt=10.0) # Higher min
    )
    # Actually wait, safety check: "If calc < min -> BLOCK" usually? 
    # Or clamp?
    # Resolver implementation:
    # "if calc < safety.min: Blocked" usually.
    # Let's check `entry_sizing_resolver.py`.
    # "if notional < profile.safety.min_notional_usdt: return Blocked(MIN_NOTIONAL)"
    
    path = ctx.entry_sizing_loader._profiles_dir / "clamp_min.json"
    with open(path, "w") as f: json.dump(p.to_dict(), f)
    ctx.entry_sizing_loader.load_all(force=True)
    
    res = ctx.entry_sizing_resolver.resolve("SOLUSDT")
    assert res.blocked
    assert "SAFETY_LIMIT" in res.block_reason

    # Max notional clamp
    # If calc > max -> Clamp to max.
    p2 = EntrySizingProfileV1(
        profile_id="clamp_max", version="1", priority=10,
        scope=EntrySizingScopeV1(symbol="ADAUSDT"),
        rule=EntrySizingRuleV1(type="fixed_notional", fixed_notional_usdt=200.0), # High
        safety=EntrySizingSafetyV1(max_notional_usdt=50.0) # Limit
    )
    path2 = ctx.entry_sizing_loader._profiles_dir / "clamp_max.json"
    with open(path2, "w") as f: json.dump(p2.to_dict(), f)
    ctx.entry_sizing_loader.load_all(force=True)
    
    res = ctx.entry_sizing_resolver.resolve("ADAUSDT")
    assert not res.blocked
    assert res.notional_usdt == 50.0 # Clamped

def test_mainnet_edit_safety(ctx):
    from tezaver.bulut.api.routes_sizing import check_mainnet_safety
    from fastapi import HTTPException
    
    # 1. Not Mainnet -> Safe
    object.__setattr__(ctx.config, "mode", "SIM")
    ctx.state.execution_armed = True
    check_mainnet_safety(ctx) # No error
    
    # 2. Mainnet, Not Armed -> Safe
    object.__setattr__(ctx.config, "mode", "REAL_MAINNET")
    ctx.state.execution_armed = False
    check_mainnet_safety(ctx) # No error
    
    # 3. Mainnet + Armed -> Blocked
    ctx.state.execution_armed = True
    
    # If using real fastapi, it raises HTTPException(409)
    # If mocked, we must ensure it behaves similarly or we catch Exception.
    # Our mock set HTTPException = Exception.
    # So we catch Exception.
    # But we can't check status_code easily on generic Exception unless we subclass.
    # Let's just check it raises.
    with pytest.raises(Exception):
        check_mainnet_safety(ctx)
