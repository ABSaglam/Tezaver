"""
Explanation Cards (Bilge Kartlar) - Turkish language interpretation layer for coin data.

This module provides human-readable Turkish summaries of persona, volatility,
patterns, and Fast15 rally data. Purely visualization/explanation layer - no trade logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st
import json
import logging

from tezaver.core.coin_cell_paths import get_coin_profile_dir
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


# ===== Translation Dictionaries =====

TRIGGER_LABELS_TR = {
    "rsi_overbought": "RSI Aşırı Alım",
    "rsi_oversold": "RSI Aşırı Satım",
    "vol_spike": "Hacim Patlaması",
    "vol_dry": "Hacim Kuruması",
    "macd_bull_cross": "MACD Boğa Kesişimi",
    "macd_bear_cross": "MACD Ayı Kesişimi",
    "macd_divergence": "MACD Diverjansı",
    "bollinger_squeeze": "Bollinger Sıkışması",
    "trend_reversal": "Trend Dönüşü",
    "ema_cross": "EMA Kesişimi",
    "support_bounce": "Destek Sekeliği",
    "resistance_break": "Direnç Kırılımı",
}

VOLATILITY_CLASS_TR = {
    "Extreme": "Ekstrem",
    "High": "Yüksek",
    "Normal": "Normal",
    "Low": "Düşük"
}

RISK_LEVEL_TR = {
    "high": "yüksek",
    "medium": "orta",
    "low": "düşük"
}

REGIME_TR = {
    "trending": "trend takipli",
    "range_bound": "aralık bağlı",
    "chaotic": "kaotik",
    "unknown": "bilinmiyor"
}


# ===== Data Context =====

@dataclass
class CoinExplanationContext:
    """Context container for all coin explanation data."""
    symbol: str
    persona: Optional[Dict[str, Any]] = None
    volatility: Optional[Dict[str, Any]] = None
    patterns: Optional[Dict[str, Any]] = None  # {trustworthy, betrayal, all_stats}
    rally_families: Optional[Dict[str, Any]] = None
    regime_profile: Optional[Dict[str, Any]] = None
    shock_profile: Optional[Dict[str, Any]] = None
    fast15_summary: Optional[Dict[str, Any]] = None
    time_labs_1h: Optional[Dict[str, Any]] = None
    time_labs_4h: Optional[Dict[str, Any]] = None
    sim_affinity: Optional[Dict[str, Any]] = None
    sim_promotion: Optional[Dict[str, Any]] = None
    rally_radar: Optional[Dict[str, Any]] = None


def _load_json_safely(path: Path) -> Optional[Dict[str, Any]]:
    """Helper to load JSON files safely without crashing."""
    if not path.exists():
        logger.debug("JSON file not found: %s", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", path, e)
        return None
    except Exception as e:
        logger.error("Unexpected error reading %s: %s", path, e)
        return None


def load_coin_explanation_context(symbol: str) -> CoinExplanationContext:
    """
    Load all explanation data for a coin from JSON files.
    
    Args:
        symbol: Coin symbol (e.g., "ETHUSDT")
    
    Returns:
        CoinExplanationContext with loaded data (None for missing files)
    """
    profile_dir = get_coin_profile_dir(symbol)
    ctx = CoinExplanationContext(symbol=symbol)
    
    # 1. Export Bulut Structure
    export_data = _load_json_safely(profile_dir / "export_bulut.json")
    if export_data:
        ctx.persona = export_data.get("persona")
        ctx.volatility = export_data.get("volatility")
        ctx.patterns = export_data.get("patterns")
        ctx.rally_families = export_data.get("rally_families")
        ctx.regime_profile = export_data.get("regime_profile")
        ctx.shock_profile = export_data.get("shock_profile")
        logger.debug(f"Loaded export_bulut.json for {symbol}")

    # 2. Fast15 Summary
    ctx.fast15_summary = _load_json_safely(profile_dir / "fast15_rallies_summary.json")

    # 3. Time-Labs Summaries
    ctx.time_labs_1h = _load_json_safely(profile_dir / "time_labs_1h_summary.json")
    ctx.time_labs_4h = _load_json_safely(profile_dir / "time_labs_4h_summary.json")

    # 4. Sim / Affinity Data
    ctx.sim_affinity = _load_json_safely(profile_dir / "sim_affinity.json")
    ctx.sim_promotion = _load_json_safely(profile_dir / "sim_promotion.json")
            
    # 5. Rally Radar
    ctx.rally_radar = _load_json_safely(profile_dir / "rally_radar.json")

    return ctx


# ===== Text Generators =====

def build_persona_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build Turkish summary from persona data.
    
    Interprets: trend_soul_score, harmony_score, betrayal_score,
               volume_trust, risk_level, opportunity_score, regime, shock_risk
    
    Returns:
        Single paragraph Turkish text, or None if no data
    """
    if not ctx.persona:
        return None
    
    try:
        p = ctx.persona
        parts = []
        
        # Trend soul
        trend_soul = p.get("trend_soul_score")
        if trend_soul is not None:
            if trend_soul >= 70:
                parts.append("**güçlü trend eğilimi** gösteriyor")
            elif trend_soul >= 40:
                parts.append("**orta düzeyde trend eğilimi** var")
            else:
                parts.append("daha çok **yatay/kararsız** hareket ediyor")
        
        # Betrayal
        betrayal = p.get("betrayal_score")
        if betrayal is not None:
            if betrayal < 30:
                parts.append("tetiklerine **sadık**")
            elif betrayal < 60:
                parts.append("**orta düzeyde** ihanet eğilimi")
            else:
                parts.append("**sık fake yapan**, dikkatli olunmalı")
        
        # Volume trust
        vol_trust = p.get("volume_trust")
        if vol_trust is not None and vol_trust >= 0.6:
            parts.append(f"hacim güvenilirliği **{vol_trust*100:.0f}%**")
        
        # Risk level
        risk_level = p.get("risk_level", "").lower()
        risk_tr = RISK_LEVEL_TR.get(risk_level, risk_level)
        if risk_tr:
            parts.append(f"toplam risk seviyesi **{risk_tr}**")
        
        # Regime
        regime = p.get("regime", "").lower()
        regime_tr = REGIME_TR.get(regime, regime)
        if regime_tr:
            parts.append(f"piyasa rejimi **{regime_tr}**")
        
        # Shock risk
        shock_risk = p.get("shock_risk")
        if shock_risk is not None and shock_risk > 7:
            parts.append("**sık şok mum** üreten bir coin")
        
        if not parts:
            return None
        
        symbol = ctx.symbol
        return f"{symbol} genel olarak " + ", ".join(parts) + "."
    
    except Exception as e:
        logger.warning(f"Error building persona summary: {e}")
        return None


def build_volatility_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build Turkish summary from volatility data.
    
    Interprets: volatility_class, avg_atr_pct, vol_spike_freq, vol_dry_freq
    
    Returns:
        2-3 sentence Turkish text, or None if no data
    """
    if not ctx.volatility:
        return None
    
    try:
        v = ctx.volatility
        lines = []
        
        # Volatility class
        vol_class = v.get("volatility_class", "")
        vol_class_tr = VOLATILITY_CLASS_TR.get(vol_class, vol_class)
        
        if vol_class == "Extreme":
            lines.append(f"Bu coin **{vol_class_tr.lower()} oynak**; kısa sürede büyük hareketler sık görülüyor.")
        elif vol_class == "High":
            lines.append(f"**{vol_class_tr} oynaklık** gösteriyor; tek bir pozisyonda stop mesafesi geniş tutulmalı.")
        elif vol_class in ["Normal", "Low"]:
            lines.append(f"Oynaklık **{vol_class_tr.lower()}** seviyede; daha sakin karakter.")
        
        # ATR
        avg_atr = v.get("avg_atr_pct")
        if avg_atr is not None:
            lines.append(f"Ortalama günlük hareket (ATR) **%{avg_atr*100:.1f}**.")
        
        # Volume behavior
        vol_spike_freq = v.get("vol_spike_freq")
        vol_dry_freq = v.get("vol_dry_freq")
        
        vol_parts = []
        if vol_spike_freq is not None and vol_spike_freq > 0.3:
            vol_parts.append(f"sık hacim patlamaları (%{vol_spike_freq*100:.0f})")
        if vol_dry_freq is not None and vol_dry_freq > 0.3:
            vol_parts.append(f"zaman zaman hacim kurumaları (%{vol_dry_freq*100:.0f})")
        
        if vol_parts:
            lines.append("Hacim davranışında " + " ve ".join(vol_parts) + " görülüyor.")
        
        return " ".join(lines) if lines else None
    
    except Exception as e:
        logger.warning(f"Error building volatility summary: {e}")
        return None


def build_patterns_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build Turkish summary from patterns data.
    
    Shows top 2-3 trustworthy patterns and worst 1-2 betrayal patterns.
    
    Returns:
        Bulleted Turkish text, or None if no data
    """
    if not ctx.patterns:
        return None
    
    try:
        trustworthy = ctx.patterns.get("trustworthy", [])
        betrayal = ctx.patterns.get("betrayal", [])
        
        lines = []
        
        # Top trustworthy patterns (max 3)
        if trustworthy:
            sorted_trust = sorted(trustworthy, key=lambda x: x.get("trust_score", 0), reverse=True)
            top_trust = sorted_trust[:3]
            
            lines.append("**Güvenilir Tetikler:**\n")
            for pattern in top_trust:
                trigger = pattern.get("trigger", "")
                trigger_tr = TRIGGER_LABELS_TR.get(trigger, trigger)
                tf = pattern.get("timeframe", "")
                samples = pattern.get("sample_count", 0)
                avg_gain = pattern.get("avg_future_max_gain_pct", 0) * 100
                hit_10p = pattern.get("hit_10p_rate", 0) * 100
                hit_20p = pattern.get("hit_20p_rate", 0) * 100
                
                line = f"- **{trigger_tr} ({tf})**: {samples} örnek, " \
                       f"ortalama +%{avg_gain:.1f} yükseliş"
                
                if hit_10p > 0:
                    line += f", %{hit_10p:.0f}'ında +%10"
                if hit_20p > 0:
                    line += f", %{hit_20p:.0f}'ında +%20 rally"
                
                lines.append(line)
        
        # Worst betrayal patterns (max 2)
        if betrayal:
            sorted_betrayal = sorted(betrayal, key=lambda x: x.get("trust_score", 1), reverse=False)
            worst_betrayal = sorted_betrayal[:2]
            
            lines.append("\n**Dikkat Edilmesi Gereken Tetikler:**\n")
            for pattern in worst_betrayal:
                trigger = pattern.get("trigger", "")
                trigger_tr = TRIGGER_LABELS_TR.get(trigger, trigger)
                tf = pattern.get("timeframe", "")
                hit_5p = pattern.get("hit_5p_rate", 0) * 100
                
                line = f"- **{trigger_tr} ({tf})**: Düşük başarı oranı " \
                       f"(%{hit_5p:.0f}'ında bile +%5 yükseliş görülmemiş), dikkatli kullanılmalı."
                lines.append(line)
        
        return "\n".join(lines) if lines else None
    
    except Exception as e:
        logger.warning(f"Error building patterns summary: {e}")
        return None


def build_fast15_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build Turkish summary from Fast15 data.
    
    Uses summary_tr if exists, adds total_events and notable bucket info.
    
    Returns:
        Paragraph Turkish text, or None if no data
    """
    if not ctx.fast15_summary:
        return None
    
    try:
        meta = ctx.fast15_summary.get("meta", {})
        total_events = meta.get("total_events", 0)
        
        if total_events == 0:
            return f"{ctx.symbol} için 15 Dakikalık Hızlı Yükseliş taramasında henüz anlamlı bir örnek bulunamadı."
        
        # Get summary_tr if exists
        summary_tr = ctx.fast15_summary.get("summary_tr", "")
        
        # Find notable bucket (highest event count or highest avg gain)
        buckets = ctx.fast15_summary.get("buckets", {})
        notable_bucket = None
        max_count = 0
        
        for bucket_name, bucket_data in buckets.items():
            count = bucket_data.get("event_count", 0)
            if count > max_count:
                max_count = count
                notable_bucket = bucket_name
        
        # Build intro
        intro = f"Bu coin için 15 dakikalık hızlı yükseliş taramasında toplam **{total_events} event** bulunmuş"
        
        if notable_bucket:
            bucket_label_map = {
                "5p_10p": "%5-10",
                "10p_20p": "%10-20",
                "20p_30p": "%20-30",
                "30p_plus": "%30+"
            }
            bucket_label = bucket_label_map.get(notable_bucket, notable_bucket)
            intro += f"; özellikle **{bucket_label} kovası** öne çıkıyor"
        
        intro += "."
        
        # Combine with summary_tr if exists
        if summary_tr:
            return f"{intro}\n\n{summary_tr}"
        else:
            return intro
    
    except Exception as e:
        logger.warning(f"Error building fast15 summary: {e}")
        return None


def build_strategy_affinity_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build Turkish summary from Strategy Affinity (Sim v1.3) data.
    
    Selects best preset (Reliable > Low Data) and formats metrics.
    """
    if not ctx.sim_affinity or "presets" not in ctx.sim_affinity:
        return None

    try:
        presets = ctx.sim_affinity["presets"]
        if not presets:
            return None
            
        # Select best preset logic
        # 1. Reliable ones
        reliable = [p for p in presets.values() if p.get("status") == "reliable"]
        
        best = None
        if reliable:
            # Sort by affinity_score desc
            best = max(reliable, key=lambda x: x.get("affinity_score", 0))
        else:
            # Fallback to low_data
            low_data = [p for p in presets.values() if p.get("status") == "low_data"]
            if low_data:
                 best = max(low_data, key=lambda x: x.get("affinity_score", 0))
                 
        if not best:
            return None
            
        # Format Text
        score = best.get("affinity_score", 0)
        grade = best.get("affinity_grade", "-")
        label = best.get("preset_id", "Unknown") # Or use label_tr if available? JSON has preset_id, scoreboard has label_tr. 
        # Wait, Sim Affinity JSON structure:
        # "presets": { "ID": { "preset_id": "...", "metrics": ... } }
        # Actually in sim_affinity.py we dumped PresetAffinity dataclass directly.
        # It has: preset_id, timeframe, num_trades, win_rate, net_pnl_pct, affinity_score, affinity_grade, status.
        # It doesn't strictly have "metrics" nested dict unless we changed it. 
        # Let's check sim_affinity.py `asdict` usage. Yes, flat structure.
        # Correction: The prompt sample JSON showed "metrics" nested. But my implementation in v1.3 used flat PresetAffinity.
        # I should output based on what I implemented in v1.3.
        # v1.3 PresetAffinity: 
        # preset_id, timeframe, num_trades, win_rate, net_pnl_pct, affinity_score, grade, status.
        # Wait, the v1.3 implementation used `asdict(summary)`. 
        # Summary has `presets: Dict[str, PresetAffinity]`.
        # So it is flat.
        
        win_rate = best.get("win_rate", 0) * 100
        net_pnl = best.get("net_pnl_pct", 0) * 100
        max_dd = best.get("max_drawdown_pct", 0) * 100
        num_trades = best.get("num_trades", 0)
        status = best.get("status", "unknown")
        
        # Friendly Name map (Optional, or just use ID)
        # We don't have label_tr in JSON unless we add it to PresetAffinity.
        # In v1.3 we didn't add label_tr to PresetAffinity dataclass! 
        # We added it to PresetScore but PresetAffinity was constructed from it.
        # Let's check sim_affinity.py. 
        # PresetAffinity has: preset_id, timeframe... NO label_tr.
        # So we use preset_id.
        
        # Sanitize text
        txt = f"{ctx.symbol} için geçmiş simülasyon sonuçlarına göre en uyumlu strateji **{label}** görünüyor " \
              f"(skor: **{score:.0f}**/100, not: **{grade}**)."
              
        txt += f" Bu strateji ile yapılan testlerde yaklaşık **%{win_rate:.1f}** başarı oranı" \
               f" ve **%{max_dd:.1f}** civarında maksimum gerileme (DD) görülmüş."
               
        if status == "low_data":
            txt += " Ancak **örnek sayısı düşük** olduğu için sonuçlar sadece fikir verme amaçlıdır, kesinlik taşımaz."
        elif status == "reliable":
             txt += f" Toplam **{num_trades} işlem** ile istatistiksel açıdan anlamlı bir veri seti oluşmuştur."
             
        # Mention alternative if close? (Complexity) -> Keep simple as requested.
        
        return txt

    except Exception as e:
        logger.warning(f"Error building strategy affinity summary: {e}")
        return None


def build_strategy_promotion_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build Turkish summary for Strategy Promotion (Sim v1.5).
    Prioritizes APPROVED -> CANDIDATE -> REJECTED.
    """
    if not ctx.sim_promotion or "strategies" not in ctx.sim_promotion:
        return None
    
    try:
        strategies = ctx.sim_promotion["strategies"]
        if not strategies:
            return None
            
        # Group by status
        approved = [s for s in strategies.values() if s.get("status") == "APPROVED"]
        candidates = [s for s in strategies.values() if s.get("status") == "CANDIDATE"]
        rejected = [s for s in strategies.values() if s.get("status") == "REJECTED"]
        
        # 1. APPROVED
        if approved:
            # Pick best by affinity score
            best = max(approved, key=lambda x: x.get("affinity_score", 0))
            
            preset = best.get("preset_id", "Unknown")
            score = best.get("affinity_score", 0)
            grade = best.get("grade", "-")
            trades = best.get("trade_count", 0)
            dd = best.get("max_drawdown_pct", 0) * 100
            rel = "güvenilir" if best.get("reliability") == "reliable" else "veri az"
            
            return (
                f"Bu coin için Bulut seviyesinde önerilen ana strateji: **{preset}** ({grade} notu, skor {score:.0f}, "
                f"{trades} işlem, {rel}). Maksimum düşüş yaklaşık %{dd:.1f}, simülasyon sonuçları istikrarlı görünüyor."
            )

        # 2. CANDIDATE
        if candidates:
            best = max(candidates, key=lambda x: x.get("affinity_score", 0))
            preset = best.get("preset_id", "Unknown")
            score = best.get("affinity_score", 0)
            
            return (
                f"Henüz kesinleşmiş onaylı bir strateji yok, ancak en güçlü aday: **{preset}** (Aday, skor {score:.0f}). "
                f"Daha fazla veri veya daha düşük risk (drawdown) bekleniyor."
            )

        # 3. REJECTED
        if rejected:
            return (
                "Şu an için simülasyon sonuçlarına göre bu coin üzerinde otomatik Bulut stratejisi önermek güvenli görünmüyor. "
                "Stratejiler izleme ve geliştirme aşamasında."
            )
            
        return None

    except Exception as e:
        logger.warning(f"Error building promotion summary: {e}")
        return None


def build_time_labs_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build integrated Turkish summary from Fast15 + Time-Labs 1h/4h data.
    
    Returns:
        Combined text paragraph or None if absolutely no data.
    """
    parts = []
    
    # 1. Fast15 (15 Minutes)
    if ctx.fast15_summary:
        f15_text = build_fast15_summary_tr(ctx)
        if f15_text:
            parts.append(f"**⚡️ 15dk Hızlı Yükselişler:**\n{f15_text}")
            
    # 2. Time-Labs 1h
    if ctx.time_labs_1h:
        try:
            meta = ctx.time_labs_1h.get("meta", {})
            count = meta.get("total_events", 0)
            summary_tr = ctx.time_labs_1h.get("summary_tr", "")
            
            if count > 0:
                parts.append(f"**🕐 1 Saat Time-Labs:**\n{summary_tr}")
            else:
                parts.append(f"**🕐 1 Saat Time-Labs:** Henüz anlamlı bir yapı bulunamadı.")
        except:
            pass
            
    # 3. Time-Labs 4h
    if ctx.time_labs_4h:
        try:
            meta = ctx.time_labs_4h.get("meta", {})
            count = meta.get("total_events", 0)
            summary_tr = ctx.time_labs_4h.get("summary_tr", "")
            
            if count > 0:
                parts.append(f"**🕓 4 Saat Time-Labs:**\n{summary_tr}")
            else:
                pass # Don't clutter if empty
        except:
            pass
            
    if not parts:
        return None
        
    return "\n\n".join(parts)


def build_rally_radar_summary_tr(ctx: CoinExplanationContext) -> Optional[str]:
    """
    Build integrated Turkish summary from Rally Radar profile.
    
    Includes environment status, dominant lane, and approved strategies.
    """
    if not ctx.rally_radar:
        return None
        
    try:
        radar = ctx.rally_radar
        overall = radar.get("overall", {})
        tfs = radar.get("timeframes", {})
        
        dominant_lane = overall.get("dominant_lane", "NONE")
        overall_status = overall.get("overall_status", "NEUTRAL")
        
        parts = []
        
        # 1. Overall & Dominant Lane Intro
        status_tr = {
            "HOT": "🔥 SICAK (Fırsat)",
            "NEUTRAL": "😐 NÖTR",
            "COLD": "❄️ SOĞUK",
            "CHAOTIC": "🌀 KAOTİK (Riskli)",
            "NO_DATA": "Yetersiz Veri"
        }.get(overall_status, overall_status)
        
        intro = f"**Rally Radar Genel Durumu:** {status_tr}"
        
        if dominant_lane != "NONE":
            lane_stats = tfs.get(dominant_lane, {})
            score = lane_stats.get("environment_score", 0)
            intro += f"\nSistem bu coin için **{dominant_lane}** zaman dilimini \"Dominant Lane\" olarak belirledi (Ortam Skoru: {score:.0f}/100)."
        
        parts.append(intro)
        
        # 2. Timeframe Breakdown
        tf_details = []
        for tf in ["4h", "1h", "15m"]:
            stats = tfs.get(tf)
            if not stats: continue
            
            st_status = stats.get("status", "NO_DATA")
            env_score = stats.get("environment_score", 0)
            
            # Icons
            icon = "⚪"
            if st_status == "HOT": icon = "🔴"
            elif st_status == "NEUTRAL": icon = "🟡"
            elif st_status == "COLD": icon = "🔵"
            elif st_status == "CHAOTIC": icon = "🌀"
            
            # Strategies
            strat_layer = stats.get("strategy_layer", {})
            approved = strat_layer.get("approved_presets", [])
            
            detail = f"{icon} **{tf}**: Skor {env_score:.0f}"
            if st_status == "CHAOTIC":
                detail += " (Kaotik/Dengesiz)"
            elif st_status == "HOT":
                detail += " (Sıcak)"
                
            if approved:
                # List approved strategies
                names = [x.get("preset_id") for x in approved]
                detail += f" — ✅ Onaylı: {', '.join(names)}"
                
            tf_details.append(detail)
            
        if tf_details:
            parts.append("Zaman Dilimi Analizi:\n" + "\n".join(tf_details))
            
        return "\n\n".join(parts)

    except Exception as e:
        logger.warning(f"Error building rally radar summary: {e}")
        return None



# ===== UI Rendering =====

def render_coin_explanation_cards(symbol: str) -> None:
    """
    Render 2x2 grid of Turkish explanation cards in Streamlit.
    
    Cards:
    - Row 1: Persona & Regime | Volatility & Volume
    - Row 2: Patterns | Time-Labs Summary (Fast15 + 1h + 4h)
    
    Args:
        symbol: Coin symbol
    """
    # Load context
    ctx = load_coin_explanation_context(symbol)
    
    # Build summaries
    persona_text = build_persona_summary_tr(ctx)
    vol_text = build_volatility_summary_tr(ctx)
    pattern_text = build_patterns_summary_tr(ctx)
    
    # Combined Time-Labs Summary
    time_labs_text = build_time_labs_summary_tr(ctx)
    
    # Strategy Affinity & Promotion & Rally Radar Summary
    strategy_text = build_strategy_affinity_summary_tr(ctx)
    promo_text = build_strategy_promotion_summary_tr(ctx)
    radar_text = build_rally_radar_summary_tr(ctx)
    
    # Priority for Final Strategy Text: 
    # Rally Radar (Top) > Promotion (Mid) > Affinity (Base)
    # If Radar exists, we can append it or use it as primary.
    # The prompt suggests: "If both sim_affinity and rally_radar exist... build common text."
    
    final_text_parts = []
    
    if radar_text:
        final_text_parts.append(radar_text)
        final_text_parts.append("---")
    
    if promo_text:
        final_text_parts.append(promo_text)
    elif strategy_text:
        final_text_parts.append(strategy_text)
        
    final_strategy_text = "\n\n".join(final_text_parts) if final_text_parts else None

    # Render header
    st.markdown("### 📊 Bilge Kartlar – Sözlü Özet")
    
    # Row 1: Persona + Volatility
    cols_row1 = st.columns(2)
    
    with cols_row1[0]:
        st.markdown("#### 🎭 Karakter & Rejim Özeti")
        if persona_text:
            st.markdown(persona_text)
        else:
            st.info("Bu kart için henüz yeterli veri yok.")
    
    with cols_row1[1]:
        st.markdown("#### 📈 Oynaklık & Hacim Davranışı")
        if vol_text:
            st.markdown(vol_text)
        else:
            st.info("Bu kart için henüz yeterli veri yok.")
    
    # Row 2: Patterns + Strategy & Time-Labs
    cols_row2 = st.columns(2)
    
    with cols_row2[0]:
        st.markdown("#### ⚡ Güvenilir / Riskli Tetikler")
        if pattern_text:
            st.markdown(pattern_text)
        else:
            st.info("Bu kart için henüz yeterli veri yok.")
    
    with cols_row2[1]:
        st.markdown("#### 🎯 Strateji Uyum & Zaman Analizi")
        
        has_content = False
        
        if final_strategy_text:
            st.markdown(final_strategy_text)
            st.markdown("---")
            has_content = True
        elif not final_strategy_text and not time_labs_text:
             st.info("Bu coin için henüz strateji uyum verisi yok. Sim Lab'de scoreboard çalıştırarak oluşturabilirsiniz.")
        
        if time_labs_text:
             st.markdown(time_labs_text)
             has_content = True
            
        if not has_content and strategy_text is None:
             # Already showed info above if both empty? 
             # logic: if strategy_text None, show info. If time_labs also None?
             # Let's clean up logic.
             pass
