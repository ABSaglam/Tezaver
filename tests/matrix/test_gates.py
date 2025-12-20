from tezaver.matrix.core.gates import (
    eval_all_gates, RiskGateConfig, GovernanceConfig, RunState, GateResult
)
import time

def test_risk_max_notional_block():
    risk = RiskGateConfig(max_notional=1000)
    gov = GovernanceConfig()
    
    # price 100 * 20 qty = 2000 > 1000
    res = eval_all_gates("BTC", 100, 20, RunState(), risk, gov, "", time.time())
    
    risk_res = next(r for r in res if r.name == "Risk:MaxNotional")
    assert not risk_res.allow
    assert "Notional 2000" in risk_res.reason

def test_allowlist_block():
    risk = RiskGateConfig()
    gov = GovernanceConfig(allowlist=["ETH"])
    
    res = eval_all_gates("BTC", 100, 1, RunState(), risk, gov, "", time.time())
    gov_res = next(r for r in res if r.name == "Gov:Allowlist")
    assert not gov_res.allow

def test_staleness_block():
    risk = RiskGateConfig()
    gov = GovernanceConfig(max_age_seconds=10)
    
    # very old ts
    old_ts = "2020-01-01T00:00:00"
    res = eval_all_gates("BTC", 100, 1, RunState(), risk, gov, old_ts, time.time())
    stale_res = next(r for r in res if r.name == "Gov:Staleness")
    assert not stale_res.allow
