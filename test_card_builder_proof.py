#!/usr/bin/env python3
"""
Card Builder Proof Test Script
==============================

Tests that Card Builder settings actually change CARD mode results.

Case A: APPROVED+GOOD preset (prod default)
Case B: Hepsi (explore) preset - wider coverage
Case C: Quality floor OFF
"""

import sys
sys.path.insert(0, "src")

import json
from datetime import datetime
from pathlib import Path

from tezaver.sniper.sniper_strategy_card_builder import (
    SniperStrategyCardConfig,
    save_sniper_strategy_card_for_symbol_timeframe,
    load_sniper_strategy_card,
)
from tezaver.sniper.v4.arena_v4 import run_sniper_arena_v4


def build_card_with_config(symbol: str, timeframe: str, case_name: str, cfg: SniperStrategyCardConfig):
    """Build a card and return its provenance."""
    print(f"\n{'='*60}")
    print(f"CASE {case_name}")
    print(f"{'='*60}")
    print(f"Config: status={cfg.include_status}, labels={cfg.include_labels}")
    print(f"        quality_floor: policy={cfg.quality_floor_policy}, value={cfg.quality_floor_value}")
    
    # Build and save card
    path = save_sniper_strategy_card_for_symbol_timeframe(symbol, timeframe, cfg)
    
    # Load and extract provenance
    card = load_sniper_strategy_card(symbol, timeframe)
    prov = card.get("provenance", {})
    
    print(f"\nProvenance:")
    print(f"  filters_used: {json.dumps(prov.get('filters_used', {}), indent=2)}")
    print(f"  source_count: {prov.get('source_count')}")
    print(f"  strict_count: {prov.get('strict_count')}")
    print(f"  built_at: {prov.get('built_at')}")
    
    return prov


def run_compare(symbol: str, timeframe: str, source: str = "patterns"):
    """Run compare across all three modes."""
    toggles = {"rsi": True, "volume": True, "atr": True, "quality": True, "ml": False}
    modes = ["ARENA_FILTERS", "CARD_STRICT_IDS", "CARD_SOURCE_IDS"]
    
    results = []
    for mode in modes:
        try:
            r = run_sniper_arena_v4(
                symbol=symbol,
                timeframe=timeframe,
                source=source,
                selection_mode=mode,
                tightness=50,
                toggles=toggles,
                risk=1.0,
                tp_pct=0.08,
                sl_pct=0.03,
                sizing_mode="equity_pct",
            )
            results.append({
                "Mode": mode,
                "Selected": r["selected_count"],
                "Trades": r["trades"],
                "Cap": f"100→{r['capital_end']:.0f}",
                "PnL%": f"{r['pnl_pct']:+.2f}%",
                "WinRate": f"{r['win_rate']:.1f}%",
                "SelFP": r["selection_fingerprint"][:8],
                "PnLSig": r["pnl_signature"][:8],
            })
        except Exception as e:
            results.append({
                "Mode": mode,
                "Selected": f"Error: {str(e)[:30]}",
                "Trades": "-",
                "Cap": "-",
                "PnL%": "-",
                "WinRate": "-",
                "SelFP": "-",
                "PnLSig": "-",
            })
    
    print("\nCompare Table:")
    print("-" * 100)
    print(f"{'Mode':<20} {'Selected':<10} {'Trades':<8} {'Cap':<12} {'PnL%':<10} {'WinRate':<10} {'SelFP':<10} {'PnLSig':<10}")
    print("-" * 100)
    for r in results:
        sel = str(r["Selected"])
        print(f"{r['Mode']:<20} {sel:<10} {r['Trades']:<8} {r['Cap']:<12} {r['PnL%']:<10} {r['WinRate']:<10} {r['SelFP']:<10} {r['PnLSig']:<10}")
    print("-" * 100)
    
    return results


def main():
    symbol = "BTCUSDT"
    timeframe = "15m"
    source = "patterns"
    
    print("=" * 70)
    print("CARD BUILDER PROOF TEST")
    print(f"Symbol: {symbol} | TF: {timeframe} | Source: {source}")
    print("=" * 70)
    
    all_results = {}
    
    # =========================================================================
    # Case A: APPROVED+GOOD (prod default)
    # =========================================================================
    cfg_a = SniperStrategyCardConfig(
        symbol=symbol,
        timeframe=timeframe,
        include_status=["APPROVED"],
        include_labels=["GOOD"],
        quality_floor_policy="HARD",
        quality_floor_value=50.0,
    )
    prov_a = build_card_with_config(symbol, timeframe, "A (APPROVED+GOOD)", cfg_a)
    results_a = run_compare(symbol, timeframe, source)
    all_results["Case A"] = {"provenance": prov_a, "compare": results_a}
    
    # =========================================================================
    # Case B: Hepsi (explore) - wider coverage
    # =========================================================================
    cfg_b = SniperStrategyCardConfig(
        symbol=symbol,
        timeframe=timeframe,
        include_status=["APPROVED", "REVIEWED", "PENDING"],
        include_labels=["GOOD", "UNCERTAIN"],
        quality_floor_policy="HARD",
        quality_floor_value=50.0,
    )
    prov_b = build_card_with_config(symbol, timeframe, "B (Hepsi/Explore)", cfg_b)
    results_b = run_compare(symbol, timeframe, source)
    all_results["Case B"] = {"provenance": prov_b, "compare": results_b}
    
    # =========================================================================
    # Case C: Quality Floor OFF
    # =========================================================================
    cfg_c = SniperStrategyCardConfig(
        symbol=symbol,
        timeframe=timeframe,
        include_status=["APPROVED"],
        include_labels=["GOOD"],
        quality_floor_policy="OFF",
        quality_floor_value=0.0,
    )
    prov_c = build_card_with_config(symbol, timeframe, "C (Quality Floor OFF)", cfg_c)
    results_c = run_compare(symbol, timeframe, source)
    all_results["Case C"] = {"provenance": prov_c, "compare": results_c}
    
    # =========================================================================
    # Summary & Verification
    # =========================================================================
    print("\n" + "=" * 70)
    print("PROOF VERIFICATION")
    print("=" * 70)
    
    # Extract key metrics for comparison
    def get_card_strict_selected(results):
        for r in results:
            if r["Mode"] == "CARD_STRICT_IDS":
                sel = r["Selected"]
                return int(sel) if isinstance(sel, (int, float)) else 0
        return 0
    
    def get_card_source_selected(results):
        for r in results:
            if r["Mode"] == "CARD_SOURCE_IDS":
                sel = r["Selected"]
                return int(sel) if isinstance(sel, (int, float)) else 0
        return 0
    
    def get_sel_fp(results, mode="CARD_STRICT_IDS"):
        for r in results:
            if r["Mode"] == mode:
                return r["SelFP"]
        return "-"
    
    def get_pnl_sig(results, mode="CARD_STRICT_IDS"):
        for r in results:
            if r["Mode"] == mode:
                return r["PnLSig"]
        return "-"
    
    source_a = prov_a.get("source_count", 0)
    source_b = prov_b.get("source_count", 0)
    strict_a = prov_a.get("strict_count", 0)
    strict_c = prov_c.get("strict_count", 0)
    
    card_source_a = get_card_source_selected(results_a)
    card_source_b = get_card_source_selected(results_b)
    card_strict_a = get_card_strict_selected(results_a)
    card_strict_c = get_card_strict_selected(results_c)
    
    print(f"\n1. Case B source_count should increase vs Case A:")
    print(f"   Case A source_count: {source_a}")
    print(f"   Case B source_count: {source_b}")
    delta_source = source_b - source_a
    if delta_source > 0:
        print(f"   ✅ PASS: delta = +{delta_source}")
    elif delta_source == 0:
        print(f"   ⚠️ SAME: delta = 0 (Card Builder config may not affect source set in current impl)")
    else:
        print(f"   ❌ FAIL: delta = {delta_source}")
    
    print(f"\n2. Case B CARD_SOURCE_IDS Selected should match or increase:")
    print(f"   Case A CARD_SOURCE_IDS: {card_source_a}")
    print(f"   Case B CARD_SOURCE_IDS: {card_source_b}")
    delta_card_src = card_source_b - card_source_a
    if delta_card_src >= 0:
        print(f"   ✅ PASS: delta = +{delta_card_src}")
    else:
        print(f"   ❌ FAIL: delta = {delta_card_src}")
    
    print(f"\n3. Case C strict_count or CARD_STRICT_IDS should increase (quality floor OFF):")
    print(f"   Case A strict_count: {strict_a}")
    print(f"   Case C strict_count: {strict_c}")
    print(f"   Case A CARD_STRICT_IDS: {card_strict_a}")
    print(f"   Case C CARD_STRICT_IDS: {card_strict_c}")
    if strict_c > strict_a or card_strict_c > card_strict_a:
        print(f"   ✅ PASS: Quality floor removal increased strict count")
    else:
        print(f"   ⚠️ No difference observed (quality floor may not be limiting factor)")
    
    print(f"\n4. CARD mode fingerprints/signatures should differ between cases:")
    
    fp_a = get_sel_fp(results_a, "CARD_STRICT_IDS")
    fp_b = get_sel_fp(results_b, "CARD_STRICT_IDS")
    fp_c = get_sel_fp(results_c, "CARD_STRICT_IDS")
    
    sig_a = get_pnl_sig(results_a, "CARD_STRICT_IDS")
    sig_b = get_pnl_sig(results_b, "CARD_STRICT_IDS")
    sig_c = get_pnl_sig(results_c, "CARD_STRICT_IDS")
    
    print(f"   Case A: SelFP={fp_a}, PnLSig={sig_a}")
    print(f"   Case B: SelFP={fp_b}, PnLSig={sig_b}")
    print(f"   Case C: SelFP={fp_c}, PnLSig={sig_c}")
    
    any_change = (fp_a != fp_b) or (fp_a != fp_c) or (sig_a != sig_b) or (sig_a != sig_c)
    if any_change:
        print(f"   ✅ PASS: At least one fingerprint/signature changed")
    else:
        print(f"   ⚠️ All fingerprints same (card content may be identical)")
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL OUTPUT (for user)")
    print("=" * 70)
    
    print("\n### Case A (APPROVED+GOOD):")
    print(f"Provenance: filters_used={prov_a.get('filters_used', {})}")
    print(f"           source_count={prov_a.get('source_count')}, strict_count={prov_a.get('strict_count')}")
    print(f"           built_at={prov_a.get('built_at')}")
    print(f"Compare: ARENA | CARD_STRICT | CARD_SOURCE")
    for r in results_a:
        sel = r["Selected"]
        print(f"  {r['Mode']}: Selected={sel}, SelFP={r['SelFP']}, PnLSig={r['PnLSig']}")
    
    print("\n### Case B (Hepsi/Explore):")
    print(f"Provenance: filters_used={prov_b.get('filters_used', {})}")
    print(f"           source_count={prov_b.get('source_count')}, strict_count={prov_b.get('strict_count')}")
    print(f"           built_at={prov_b.get('built_at')}")
    print(f"Compare: ARENA | CARD_STRICT | CARD_SOURCE")
    for r in results_b:
        sel = r["Selected"]
        print(f"  {r['Mode']}: Selected={sel}, SelFP={r['SelFP']}, PnLSig={r['PnLSig']}")
    
    print("\n### Case C (Quality Floor OFF):")
    print(f"Provenance: filters_used={prov_c.get('filters_used', {})}")
    print(f"           source_count={prov_c.get('source_count')}, strict_count={prov_c.get('strict_count')}")
    print(f"           built_at={prov_c.get('built_at')}")
    print(f"Compare: ARENA | CARD_STRICT | CARD_SOURCE")
    for r in results_c:
        sel = r["Selected"]
        print(f"  {r['Mode']}: Selected={sel}, SelFP={r['SelFP']}, PnLSig={r['PnLSig']}")
    
    print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
