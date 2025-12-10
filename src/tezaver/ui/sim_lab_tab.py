"""
Tezaver Coin Lab UI Tab
=======================

Clean coin-focused analysis panel.
- Timeframe selector (15m / 1h / 4h)
- Coin Fingerprint (rally context sweet spots)
- Grade Cards (Diamond / Gold / Silver / Bronze)
"""

import json
import streamlit as st
import pandas as pd
from pathlib import Path

from tezaver.rally.rally_grade_cards import compute_btc_15m_grade_summaries
from tezaver.matrix.wargame.runner import SILVER_MULTI_COIN_SUMMARY_PATH


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def render_sim_lab_tab(symbol: str):
    """
    Coin Lab görünümü:
    - Timeframe seçimi (en üstte)
    - Header + Fingerprint (yan yana expander)
    - Grade kartları (2x2 expander)
    - Silver Bilgeliği (expander)
    - Deneyler (expander)
    """
    # 1. En üstte: Timeframe seçimi
    tf = st.radio(
        "⏱️ Zaman Dilimi",
        options=["15m", "1h", "4h"],
        index=0,
        horizontal=True,
        key="coin_lab_timeframe",
    )
    
    st.divider()
    
    # 2. Header + Fingerprint yan yana expander
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("🧪 Coin Lab Hakkında", expanded=False):
            render_sim_lab_header()
    
    with col2:
        with st.expander(f"📊 Fingerprint – {tf}", expanded=True):
            render_coin_fingerprint_section(symbol, tf)
    
    st.divider()
    
    # 3. Grade kartları (2x2 expander, sayılarla)
    render_grade_cards_section(symbol, tf)
    
    # 4. Silver Bilgeliği (tüm TF'ler için, expander içinde)
    if symbol == "BTCUSDT" and tf in ["15m", "1h", "4h"]:
        st.divider()
        with st.expander(f"🥈 Silver Bilgeliği – {tf} Hikâye & Strateji Kartı", expanded=False):
            render_silver_story_card(symbol, tf)
            st.markdown("---")
            render_silver_strategy_card(symbol, tf)
    
    # 5. Deneyler (tüm TF'ler için, expander içinde)
    if symbol == "BTCUSDT" and tf in ["15m", "1h", "4h"]:
        st.divider()
        with st.expander(f"🧪 Deneyler – {tf} Silver Strateji Sim", expanded=False):
            render_core_strategy_section(symbol, tf)
            
            # ML A/B Test sadece 15m için
            if tf == "15m":
                st.markdown("---")
                render_silver_ml_ab_test_section(symbol, tf)
    
    # 6. Matrix Preview (15m için)
    if tf == "15m":
        st.divider()
        render_silver_15m_matrix_preview(symbol, tf)



# =============================================================================
# HEADER SECTION
# =============================================================================

def render_sim_lab_header():
    """Coin Lab açıklaması."""
    st.subheader("🧪 Coin Lab – BTC Rally Fotoğrafı")
    st.markdown(
        """
        Bu panel coin'den gelen rally verisini **analiz eder ve görselleştirir**.

        - **Fingerprint Kartı:** Timeframe'e göre tatlı bölgeleri gösterir
        - **Grade Kartları:** Rally'leri performansa göre kategorize eder
        
        Şu anki haliyle Coin Lab bir **okuma paneli**dir; strateji ve Matrix entegrasyonu sonraki adımlarda eklenecektir.
        """
    )


# =============================================================================
# COIN FINGERPRINT SECTION
# =============================================================================

def render_coin_fingerprint_section(symbol: str, timeframe: str = "15m") -> None:
    """
    Seçilen symbol + timeframe için parmak izi kartını gösterir.
    """
    tf_label = {
        "15m": "15 Dakika",
        "1h": "1 Saat",
        "4h": "4 Saat",
    }.get(timeframe, timeframe)
    
    if symbol != "BTCUSDT":
        st.subheader("🧬 Coin Parmak İzi")
        st.info("Coin Lab fingerprint kartı şu anda yalnızca BTCUSDT için tanımlı.")
        return

    st.subheader(f"🧬 Coin Parmak İzi – BTC {tf_label}")

    # Fingerprint ID
    tf_upper = timeframe.upper()
    fingerprint_id = f"BTC{tf_upper}_FP_CORE_V1"
    st.markdown(f"**Fingerprint ID:** `{fingerprint_id}`")

    # JSON path
    base_dir = Path("data/coin_profiles") / "BTCUSDT" / timeframe
    report_path = base_dir / "rally_context_score_report_v1.json"

    if not report_path.exists():
        st.warning(
            f"BTCUSDT {tf_label} için rally context raporu bulunamadı.\n\n"
            f"Beklenen dosya: `{report_path}`\n\n"
            "Bu timeframe için offline analiz pipeline'ını çalıştırdıktan sonra "
            "parmak izi kartı aktif olacaktır."
        )
        return

    try:
        report = json.loads(report_path.read_text())
    except Exception as e:
        st.error(f"Parmak izi raporu okunamadı: {e}")
        return

    metrics = report.get("metrics", {})

    def _get_sweet(mname):
        m = metrics.get(mname, {})
        ss = m.get("recommended_sweet_spot")
        if not ss or len(ss) != 2:
            return None
        return ss

    # Timeframe'e göre metrik isimleri
    if timeframe == "15m":
        rsi_key, vol_key, atr_key = "rsi_15m", "volume_rel_15m", "atr_pct_15m"
    elif timeframe == "1h":
        rsi_key, vol_key, atr_key = "rsi_1h", "volume_rel_1h", "atr_pct_1h"
    elif timeframe == "4h":
        rsi_key, vol_key, atr_key = "rsi_4h", "volume_rel_4h", "atr_pct_4h"
    else:
        rsi_key, vol_key, atr_key = "rsi", "volume_rel", "atr_pct"

    rsi_ss = _get_sweet(rsi_key) or _get_sweet("rsi")
    vol_ss = _get_sweet(vol_key) or _get_sweet("volume_rel")
    atr_ss = _get_sweet(atr_key) or _get_sweet("atr_pct")
    score_ss = _get_sweet("quality_score")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**RSI Tatlı Bölge**")
        if rsi_ss:
            st.write(f"{rsi_ss[0]:.1f} – {rsi_ss[1]:.1f}")
        else:
            st.write("Tanımlı değil")

        st.markdown("**Relative Volume Tatlı Bölge**")
        if vol_ss:
            st.write(f"{vol_ss[0]:.2f} – {vol_ss[1]:.2f}")
        else:
            st.write("Tanımlı değil")

    with col2:
        st.markdown("**ATR % Tatlı Bölge**")
        if atr_ss:
            st.write(f"{atr_ss[0]:.2f}% – {atr_ss[1]:.2f}%")
        else:
            st.write("Tanımlı değil")

        st.markdown("**Quality Score Tatlı Bölge**")
        if score_ss:
            st.write(f"{score_ss[0]:.1f} – {score_ss[1]:.1f}")
        else:
            st.write("Tanımlı değil")

    st.caption(
        f"Bu parmak izi kartı, BTC {tf_label} zaman dilimindeki iyi rally'lerin "
        "ortak özelliklerini özetler."
    )


# =============================================================================
# GRADE CARDS SECTION
# =============================================================================

def render_grade_cards_section(symbol: str, timeframe: str) -> None:
    """
    Diamond / Gold / Silver / Bronze grade kartlarını 2x2 expander olarak gösterir.
    Her expander başlığında grade ismi ve örnek sayısı görünür.
    """
    if symbol != "BTCUSDT":
        st.info("Grade kartları şu anda yalnızca BTCUSDT için tanımlı.")
        return

    if timeframe != "15m":
        st.info(
            "Grade kartları ilk aşamada sadece 15 Dakika için aktif. "
            "1 Saat ve 4 Saat desteği daha sonra eklenecek."
        )
        return

    try:
        summaries = compute_btc_15m_grade_summaries()
    except FileNotFoundError as e:
        st.warning(str(e))
        return
    except Exception as e:
        st.error(f"Grade kartları hesaplanırken hata oluştu: {e}")
        return

    grade_order = ["Diamond", "Gold", "Silver", "Bronze"]
    grade_emojis = {
        "Diamond": "💎",
        "Gold": "🥇",
        "Silver": "🥈",
        "Bronze": "🥉",
    }

    # 2x2 grid: first row
    row1_col1, row1_col2 = st.columns(2)
    # 2x2 grid: second row
    row2_col1, row2_col2 = st.columns(2)
    
    cols_map = {
        "Diamond": row1_col1,
        "Gold": row1_col2,
        "Silver": row2_col1,
        "Bronze": row2_col2,
    }

    for grade in grade_order:
        summary = summaries.get(grade)
        col = cols_map[grade]
        emoji = grade_emojis.get(grade, "🏅")
        
        # Count for title
        count = summary.count if summary and summary.has_enough_samples else 0
        title = f"{emoji} {grade} ({count} rally)"
        
        with col:
            with st.expander(title, expanded=False):
                if summary is None or not summary.has_enough_samples or summary.count == 0:
                    st.write("Bu grade için yeterli rally örneği yok.")
                    continue

                st.markdown(
                    f"**Tepe Kazanç:** "
                    f"{summary.min_gain_pct:.1f}% – {summary.max_gain_pct:.1f}% "
                    f"(ort: {summary.avg_gain_pct:.1f}%)"
                )
                st.markdown(f"**Ort. Tepeye Ulaşma:** {summary.avg_bars_to_peak:.1f} bar")

                if summary.rsi_p25 is not None and summary.rsi_p75 is not None:
                    st.markdown(f"**RSI:** {summary.rsi_p25:.1f} – {summary.rsi_p75:.1f}")

                if summary.vol_p25 is not None and summary.vol_p75 is not None:
                    st.markdown(f"**Vol Rel:** {summary.vol_p25:.2f} – {summary.vol_p75:.2f}")

                if summary.atr_p25 is not None and summary.atr_p75 is not None:
                    st.markdown(f"**ATR %:** {summary.atr_p25:.2f}% – {summary.atr_p75:.2f}%")

                if summary.quality_p25 is not None and summary.quality_p75 is not None:
                    st.markdown(f"**Quality:** {summary.quality_p25:.1f} – {summary.quality_p75:.1f}")


# =============================================================================
# SILVER ML A/B TEST SECTION
# =============================================================================

def render_silver_ml_ab_test_section(symbol: str, timeframe: str) -> None:
    """
    BTCUSDT 15m Silver Strategy + ML filter A/B test UI.
    Compares 4 scenarios: baseline, ml_atr, ml_atr_rsi1h, ml_all.
    """
    if symbol != "BTCUSDT" or timeframe != "15m":
        return

    st.subheader("🔬 Silver ML Filter A/B Test – BTC 15 Dakika")
    st.caption(
        "Aynı Silver stratejiyi 4 farklı ML filtre kombinasyonu ile test eder:\n"
        "- **baseline:** ML filtresi yok\n"
        "- **ml_atr:** Sadece ATR 15m ML bandı\n"
        "- **ml_atr_rsi1h:** ATR + RSI 1H ML bandı\n"
        "- **ml_all:** ATR + RSI 1H + 1D RSI Gap"
    )

    if st.button("🔬 Silver ML A/B Testini Çalıştır", key="btn_silver_ml_ab", use_container_width=True):
        with st.spinner("Silver ML A/B testi çalışıyor..."):
            from tezaver.sim.sim_silver_ml_ab_experiments import run_btc_15m_silver_ml_ab_test
            summary = run_btc_15m_silver_ml_ab_test()

        scenarios = summary.get("scenarios", {})

        import pandas as pd

        rows = []
        for key, s in scenarios.items():
            capital_end = s.get("capital_end", 100.0)
            rows.append({
                "Senaryo": key,
                "Events": s["event_count"],
                "Trades": s["trade_count"],
                "Win Rate %": round(s["win_rate"] * 100, 1),
                "Avg PnL %": round(s["avg_pnl"] * 100, 2),
                "Sum PnL %": round(s["sum_pnl"] * 100, 2),
                "Max DD %": round(s["max_drawdown"] * 100, 2),
                "💰 100 → X": f"{capital_end:.1f}",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        st.info(
            "💡 **Not:** ML filtreleri uyguldıkça trade sayısı düşer, "
            "avg_pnl artabilir. '100 → X' sermaye simülasyonu."
        )


# =============================================================================
# GENERIC MULTI-TIMEFRAME SECTIONS
# =============================================================================

def render_silver_story_card(symbol: str, timeframe: str) -> None:
    """Generic Silver Story Card for any timeframe."""
    if symbol != "BTCUSDT":
        st.info("Silver Story şu anda sadece BTCUSDT için destekleniyor.")
        return

    from tezaver.rally.rally_grade_cards import compute_silver_story_v1
    
    try:
        story = compute_silver_story_v1(symbol, timeframe)
    except Exception as e:
        st.warning(f"Silver Story yüklenemedi: {e}")
        return
    
    if not story.get("has_enough_samples", False):
        st.info(f"{timeframe} için yeterli Silver rally bulunamadı.")
        return
    
    st.markdown(f"**🥈 Silver Story – {timeframe}**")
    st.write(f"Sample Count: **{story.get('sample_count', 0)}**")
    
    static_key = f"static_snapshot_{timeframe}"
    static = story.get(static_key, {})
    
    if static:
        cols = list(static.keys())[:4]
        if cols:
            col_objs = st.columns(len(cols))
            for i, col in enumerate(cols):
                stats = static.get(col, {})
                with col_objs[i]:
                    st.caption(col)
                    if stats:
                        mean = stats.get("mean", 0)
                        p25 = stats.get("p25", 0) 
                        p75 = stats.get("p75", 0)
                        st.write(f"mean: {mean:.2f}")
                        st.write(f"[{p25:.2f}, {p75:.2f}]")


def render_silver_strategy_card(symbol: str, timeframe: str) -> None:
    """Generic Silver Strategy Card for any timeframe."""
    if symbol != "BTCUSDT":
        return

    from tezaver.rally.rally_grade_cards import load_silver_strategy_card_v1
    
    card = load_silver_strategy_card_v1(symbol, timeframe)
    
    if not card or not card.get("ok", False):
        st.info(f"{timeframe} Strategy Card bulunamadı. Önce 'python -m tezaver.rally.rally_grade_cards' çalıştırın.")
        return
    
    st.markdown(f"**📋 Strategy Card – {timeframe}**")
    
    risk = card.get("risk", {})
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("TP", f"{risk.get('tp_pct', 0)*100:.1f}%")
    with col2:
        st.metric("SL", f"{risk.get('sl_pct', 0)*100:.1f}%")
    with col3:
        st.metric("Horizon", f"{risk.get('max_horizon_bars', 0)} bar")
    
    with st.expander("📜 Card JSON", expanded=False):
        st.json(card)


def render_core_strategy_section(symbol: str, timeframe: str) -> None:
    """Generic Core Strategy test section for any timeframe."""
    if symbol != "BTCUSDT":
        st.info("Core Strategy şu anda sadece BTCUSDT için destekleniyor.")
        return
    
    st.markdown(f"**⚙️ Core Strategy Test – {timeframe}**")
    st.caption(f"Silver Strategy Card {timeframe}'ten config alarak simülasyon çalıştırır.")
    
    btn_key = f"btn_core_strategy_{timeframe}"
    if st.button(f"⚙️ {timeframe} Stratejiyi Test Et", key=btn_key):
        with st.spinner(f"{timeframe} Silver strateji simülasyonu çalışıyor..."):
            from tezaver.sim.sim_core_experiments import run_btc_core_strategy_sim
            result = run_btc_core_strategy_sim(timeframe)
        
        if not result.get("ok", False):
            st.warning(f"Strateji testi çalıştırılamadı: {result.get('reason', 'unknown')}")
            return
        
        perf = result.get("performance", {})
        event_count = result.get("event_count", 0)
        
        trade_count = perf.get("trade_count", 0)
        win_rate = perf.get("win_rate", 0.0) or 0.0
        avg_pnl = perf.get("avg_pnl", 0.0) or 0.0
        sum_pnl = perf.get("sum_pnl", 0.0) or 0.0
        max_dd = perf.get("max_drawdown", 0.0) or 0.0
        capital_end = perf.get("capital_end", 100.0) or 100.0
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric("Trade", trade_count)
        with col2:
            st.metric("Win Rate", f"{win_rate * 100:.1f}%")
        with col3:
            st.metric("Avg PnL", f"{avg_pnl:.1f}%")
        with col4:
            st.metric("Sum PnL", f"{sum_pnl:.1f}%")
        with col5:
            st.metric("Max DD", f"{max_dd:.1f}%")
        with col6:
            st.metric("💰 Sermaye", f"100 → {capital_end:.1f}")
        
        st.caption(f"{event_count} event test edildi.")


# =============================================================================
# SILVER 15M MATRIX PREVIEW SECTION
# =============================================================================

def render_silver_15m_matrix_preview(symbol: str, timeframe: str) -> None:
    """
    Silver 15m Multi-Coin Matrix preview card.
    Shows War Game results for BTC/ETH/SOL.
    """
    if timeframe != "15m":
        return
    
    if not SILVER_MULTI_COIN_SUMMARY_PATH.exists():
        st.info(
            "🧭 Silver 15m Matrix ön izlemesi için henüz War Game özeti bulunamadı.\n\n"
            "CLI ile üret:\n"
            "```bash\n"
            "python -m tezaver.matrix.wargame.runner multi_silver_15m_save\n"
            "```"
        )
        return
    
    try:
        with SILVER_MULTI_COIN_SUMMARY_PATH.open("r", encoding="utf-8") as f:
            summary = json.load(f)
    except Exception as e:
        st.error(f"Summary okunamadı: {e}")
        return
    
    rows = summary.get("coins", [])
    
    # Sadece 0.01 risk satırları
    low_risk_rows = [
        r for r in rows
        if abs(r.get("risk", 0.0) - 0.01) < 1e-9
    ]
    
    if not low_risk_rows:
        st.info("Silver 15m Matrix ön izlemesi için 0.01 risk satırı bulunamadı.")
        return
    
    st.subheader("🧭 Silver 15m – Matrix Preview")
    
    st.caption(
        "Bu kart, Silver 15m stratejisinin Matrix War Game sonuçlarını özetler. "
        "Her satır, coin başına 100 birim sermaye ve %1 risk ile koşulan testin sonucudur."
    )
    
    df = pd.DataFrame([
        {
            "Coin": row.get("symbol"),
            "Risk": f"{row.get('risk', 0):.2%}",
            "100 → X": f"100.00 → {row.get('capital_end', 0):.2f}",
            "PnL %": f"{row.get('pnl_pct', 0.0):+.2f}%",
            "Max DD %": f"{row.get('max_dd_pct', 0.0):.2f}%",
            "Trades": row.get("trades"),
        }
        for row in low_risk_rows
    ])
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Highlight current symbol
    current_row = next((r for r in low_risk_rows if r.get("symbol") == symbol), None)
    if current_row:
        st.caption(
            f"📍 **{symbol}**: 100 → {current_row.get('capital_end', 0):.2f} "
            f"({current_row.get('pnl_pct', 0.0):+.2f}%), "
            f"{current_row.get('trades')} trade"
        )


