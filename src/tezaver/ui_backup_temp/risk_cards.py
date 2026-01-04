"""
Risk Cards UI Module (v0.1)
===========================

This module implements the "Decision Book" logic for the Risk Panel.
It aggregates existing offline lab data into a comprehensive risk profile
with Volatility, Fakeout, and Strategy risk dimensions.

Purely visualization and interpretation layer. No new pipelines.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st
import pandas as pd

from tezaver.core.coin_cell_paths import get_coin_profile_dir
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

# --- Data Context ---

@dataclass
class CoinRiskContext:
    """Holds all raw data required for risk assessment."""
    symbol: str
    persona: Optional[Dict[str, Any]] = None
    volatility: Optional[Dict[str, Any]] = None
    shock_profile: Optional[Dict[str, Any]] = None
    rally_summaries: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)
    sim_affinity: Optional[Dict[str, Any]] = None
    sim_promotion: Optional[Dict[str, Any]] = None


def load_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading {path}: {e}")
        return None


def load_coin_risk_context(symbol: str) -> CoinRiskContext:
    """Load all necessary JSON files for risk analysis."""
    p_dir = get_coin_profile_dir(symbol)
    ctx = CoinRiskContext(symbol=symbol)

    # 1. Export Bulut (Persona, Volatility, Shock)
    export_data = load_json_safe(p_dir / "export_bulut.json")
    if export_data:
        ctx.persona = export_data.get("persona")
        ctx.volatility = export_data.get("volatility")
        ctx.shock_profile = export_data.get("shock_profile")

    # 2. Rally Summaries
    ctx.rally_summaries["fast15"] = load_json_safe(p_dir / "fast15_rallies_summary.json")
    ctx.rally_summaries["1h"] = load_json_safe(p_dir / "time_labs_1h_summary.json")
    ctx.rally_summaries["4h"] = load_json_safe(p_dir / "time_labs_4h_summary.json")

    # 3. Sim Data
    ctx.sim_affinity = load_json_safe(p_dir / "sim_affinity.json")
    ctx.sim_promotion = load_json_safe(p_dir / "sim_promotion.json")

    return ctx


# --- Core Logic helpers ---

def clamp(val, low=0, high=100):
    return max(low, min(val, high))


# --- Risk Models ---

def compute_volatility_risk(ctx: CoinRiskContext) -> Tuple[Optional[int], str]:
    """
    Compute Volatility Risk Score (0-100).
    Returns: (score, summary_text)
    """
    if not ctx.volatility:
        return None, "Bu kart için henüz yeterli veri yok."

    v = ctx.volatility
    vol_class = v.get("volatility_class", "Normal")
    avg_atr = v.get("avg_atr_pct", 0.0)
    spike_freq = v.get("vol_spike_freq", 0.0)

    # Base Score
    base_map = {
        "Extreme": 85,
        "High": 70,
        "Normal": 45,
        "Low": 25
    }
    score = base_map.get(vol_class, 45)

    # ATR adjustment
    if avg_atr > 0.06:
        score += 10
    elif avg_atr < 0.02:
        score -= 10

    score = clamp(score, 0, 100)

    # Text Generation
    atr_pct = avg_atr * 100
    spike_pct = spike_freq * 100
    
    vol_tr_map = {
        "Extreme": "ekstrem", "High": "yüksek", 
        "Normal": "normal", "Low": "düşük"
    }
    vol_tr = vol_tr_map.get(vol_class, "belirsiz")

    text = (
        f"Bu coin **{vol_tr} oynaklık** sınıfındadır; ortalama günlük hareket (ATR) **%{atr_pct:.1f}** seviyesindedir. "
    )
    
    if spike_freq > 0.3:
        text += f"Zaman zaman belirgin **hacim patlamaları (%{spike_pct:.0f})** görülmektedir. "
    
    if score >= 60:
        text += "Kısa vadeli işlemlerde stop mesafesi geniş tutulmalı, kaldıraç kullanımı risklidir."
    else:
        text += "Fiyat hareketleri genellikle istikrarlı bir seyir izler."

    return score, text


def compute_shock_fakeout_risk(ctx: CoinRiskContext) -> Tuple[Optional[int], str]:
    """
    Compute Shock & Fakeout Risk Score (0-100).
    Returns: (score, summary_text)
    """
    p = ctx.persona or {}
    betrayal = p.get("betrayal_score", 50)  # Default neutral
    
    # Analyze Rally Shapes for "Spike" or "Weak"
    # Prefer Fast15 data for fakeout sensitivity, fall back to 1h
    r_sum = ctx.rally_summaries.get("fast15")
    
    spike_weak_ratio = 0.0
    avg_quality = 50.0 # moderate default
    total_events = 0
    
    if r_sum and "shape_distribution" in r_sum:
        shapes = r_sum["shape_distribution"]
        total = r_sum.get("meta", {}).get("total_events", 0)
        total_events = total
        
        if total > 0:
            s_count = shapes.get("spike", 0)
            w_count = shapes.get("weak", 0)
            spike_weak_ratio = (s_count + w_count) / total
            
            # Extract quality if present
            # Usually inside bucket stats or meta, let's look for average quality in meta if added
            # If not, ignore quality adjustment
            pass
            
    # Model
    # risk = 0.6 * betrayal + 0.25 * (bad_ratio*100)
    risk_val = (0.6 * betrayal) + (0.25 * (spike_weak_ratio * 100))
    
    # Adjust for low quality if we had it, but let's stick to simple
    score = clamp(int(risk_val), 0, 100)
    
    # Text
    fake_pct = spike_weak_ratio * 100
    
    text = f"Bu coin "
    if score > 60:
        text += "**yüksek fakeout (aldatmaca)** eğilimi gösteriyor. "
    elif score > 40:
        text += "**orta seviyede** fakeout riski taşıyor. "
    else:
        text += "genellikle **temiz ve güvenilir** hareket ediyor. "
        
    text += f"Betrayal (İhanet) skoru **{betrayal}**. "
    
    if total_events > 0:
        text += f"Son tespit edilen hızlı rallilerin yaklaşık **%{fake_pct:.0f}'i** zayıf veya iğne (spike) şeklinde sonuçlanmış. "
        if score > 50:
            text += "Özellikle dar stop'lu stratejilerde dikkatli olunmalı."
    else:
        text += "Detaylı fakeout analizi için yeterli rally verisi bulunmuyor."
        
    return score, text


def compute_strategy_risk(ctx: CoinRiskContext) -> Tuple[Optional[int], str]:
    """
    Compute Strategy Risk Profile (Sim).
    Returns: (score, summary_text)
    """
    # 1. Find Best Strategy (Approved > Candidate)
    strategies = {}
    if ctx.sim_promotion and "strategies" in ctx.sim_promotion:
        strategies = ctx.sim_promotion["strategies"]
    
    best_strat = None
    
    # Look for APPROVED
    approved = [s for s in strategies.values() if s.get("status") == "APPROVED"]
    if approved:
        best_strat = max(approved, key=lambda x: x.get("affinity_score", 0))
    else:
        # Candidate
        candidates = [s for s in strategies.values() if s.get("status") == "CANDIDATE"]
        if candidates:
            best_strat = max(candidates, key=lambda x: x.get("affinity_score", 0))
            
    if not best_strat:
        return None, "Bu coin için henüz risk açısından güvenilir kabul edilen bir strateji bulunmuyor. Simülasyon verisi yetersiz olabilir."

    # Extract Metrics
    dd = abs(best_strat.get("max_drawdown_pct", 0.0))
    win = best_strat.get("win_rate", 0.0)
    count = best_strat.get("trade_count", 0)
    pid = best_strat.get("preset_id", "Unknown")
    grade = best_strat.get("grade", "-")
    status = best_strat.get("status", "Unknown")

    # Scoring Model
    # Base from DD
    if dd <= 0.15: base = 30
    elif dd <= 0.25: base = 55
    else: base = 80
    
    score = base
    
    if win > 0.60: score -= 5
    if win < 0.40: score += 5
    
    if count < 30: score += 10 # Low data penalty
    
    score = clamp(score, 0, 100)
    
    # Text
    dd_pct = dd * 100
    win_pct = win * 100
    
    risk_label = "DÜŞÜK"
    if score > 66: risk_label = "YÜKSEK"
    elif score > 33: risk_label = "ORTA"
    
    status_label = "Onaylı" if status == "APPROVED" else "Aday"
    
    text = (
        f"{status_label} strateji: **{pid} ({grade} notu)**. "
        f"Maksimum tarihsel düşüş: **-%{dd_pct:.1f}**, Başarı oranı: **%{win_pct:.1f}** ({count} işlem). "
        f"Bu kombinasyon **{risk_label} RİSKLİ**, sisteme özgü bir yaklaşım sunuyor. "
    )
    
    if count < 30:
        text += "İşlem sayısı az olduğu için sonuçlara temkinli yaklaşılmalı."
    elif score > 60:
        text += "Düşüş dönemlerinde sabır gerektirebilir."
    else:
        text += "İstikrarlı bir büyüme eğilimi görülüyor."
        
    return score, text


def build_overall_risk_summary_tr(v_score, s_score, st_score) -> str:
    """Synthesize overall risk text."""
    valid_scores = [x for x in [v_score, s_score, st_score] if x is not None]
    
    if not valid_scores:
        return "Genel Risk: **BİLİNMİYOR** (Veri Yok). Lütfen sistemin veri toplamasını bekleyin."
        
    avg_score = sum(valid_scores) / len(valid_scores)
    
    label = "DÜŞÜK"
    if avg_score > 66: label = "YÜKSEK"
    elif avg_score > 33: label = "ORTA"
    
    # Dynamic description
    details = []
    if v_score and v_score > 60: details.append("yüksek oynaklık")
    if s_score and s_score > 60: details.append("fakeout riski")
    if st_score and st_score > 60: details.append("stratejik zorluklar")
    
    desc = ""
    if details:
        desc = f"Öne çıkan risk faktörleri: {', '.join(details)}."
    else:
        desc = "Genel olarak dengeli bir risk profili görülüyor."
        
    return f"Genel Risk: **{label}**. {desc}"


# --- UI Rendering ---

def render_risk_tab(symbol: str):
    """
    Main entry point to render the Risk Tab in Streamlit.
    """
    ctx = load_coin_risk_context(symbol)
    
    # Compute Scores
    v_score, v_text = compute_volatility_risk(ctx)
    s_score, s_text = compute_shock_fakeout_risk(ctx)
    st_score, st_text = compute_strategy_risk(ctx)
    
    # Overall Summary
    summary_tr = build_overall_risk_summary_tr(v_score, s_score, st_score)
    
    # --- RENDER ---
    
    # 1. Top Summary
    st.info(f"🛡️ {summary_tr}")
    
    st.markdown("---")
    
    # 2. Main Risk Axes (2 Cols)
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("📉 Fiyat & Oynaklık")
        if v_score is not None:
            # Gauge-like progress bar
            st.progress(v_score / 100, text=f"Risk Skoru: {v_score}/100")
            st.markdown(v_text)
        else:
            st.warning(v_text)
            
    with c2:
        st.subheader("⚡ Şok & Fakeout")
        if s_score is not None:
            st.progress(s_score / 100, text=f"Risk Skoru: {s_score}/100")
            st.markdown(s_text)
        else:
            st.warning(s_text)
            
    st.markdown("---")
    
    # 3. Strategy Risk (Full Width)
    st.subheader("🤖 Strateji Risk Profili (Sim)")
    if st_score is not None:
        st.progress(st_score / 100, text=f"Risk Skoru: {st_score}/100")
        st.markdown(st_text)
    else:
        st.warning(st_text)

    # Footer note
    st.markdown("---")
    st.caption("⚠️ **Yasal Uyarı:** Bu risk değerlendirmesi sadece tarihsel sistem verilerine dayanır. Yatırım tavsiyesi değildir.")
