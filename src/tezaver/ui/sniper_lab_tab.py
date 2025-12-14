"""
Tezaver Sniper Lab V2 - Professional Annotation Workflow
=========================================================
Left/Right layout with status/label workflow for manual entry marking.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional

from tezaver.ui.chart_area import render_sniper_studio_chart, load_history_data
from tezaver.sniper.sniper_annotations import (
    SniperAnnotation,
    SniperAnnotationRepository,
)
from tezaver.rally.rally_pattern_loader import (
    load_silver_events,
    SilverEventSummary,
)


def render_sniper_lab_tab(symbol: str):
    """🎯 Sniper Lab V2 - Professional Annotation Workflow"""
    
    # Timeframe tabs
    tab_15m, tab_1h, tab_4h = st.tabs(["⏱️ 15m", "⏱️ 1h", "⏱️ 4h"])
    
    with tab_15m:
        _render_sniper_content(symbol, "15m")
    
    with tab_1h:
        _render_sniper_content(symbol, "1h")
    
    with tab_4h:
        _render_sniper_content(symbol, "4h")


def _render_sniper_content(symbol: str, tf: str):
    """Render Sniper Lab content for a specific timeframe."""
    repo = SniperAnnotationRepository()
    events = load_silver_events(symbol, tf)
    
    if not events:
        st.warning(f"{symbol} {tf} için rally verisi bulunamadı.")
        return
    
    # Rally List
    render_event_list(symbol, tf, events, repo)
    
    st.divider()
    
    # Chart + Editor
    render_chart_and_editor(symbol, tf, events, repo)


def render_sniper_backtest_section(symbol: str, timeframe: str):
    """Sniper Backtest UI section."""
    from pathlib import Path
    
    card_path = Path(f"data/coin_profiles/{symbol.upper()}/{timeframe}/sniper_strategy_card_v1.json")
    entries_path = Path(f"data/ai_datasets/{symbol.upper()}/{timeframe}/sniper_entries_v1.parquet")
    
    with st.expander("🎯 Sniper Backtest – 100 → X", expanded=False):
        st.caption("Sniper kartına göre, seçtiğin risk ile 100 birim sermaye geçmişte ne olurdu?")
        
        # Check if prerequisites exist
        if not entries_path.exists():
            st.info(
                "Sniper entries dataset henüz oluşturulmamış. "
                "CLI ile oluştur: `python -m tezaver.sniper SYMBOL TIMEFRAME`"
            )
            return
        
        if not card_path.exists():
            st.warning(
                "Sniper strateji kartı henüz oluşturulmamış. "
                "Önce Sniper Lab'de annotation yap, sonra CLI ile kartı oluştur."
            )
            # Still allow backtest without card (uses all entries)
        
        col1, col2 = st.columns(2)
        with col1:
            risk = st.slider(
                "Risk / Trade (equity oranı)",
                min_value=0.01,
                max_value=1.0,
                value=1.0,
                step=0.01,
                help="Her işlemde kullanılacak sermaye oranı (1.0 = %100)",
                key=f"sniper_risk_{symbol}_{timeframe}",
            )
        with col2:
            st.write("")  # spacer
            run_btn = st.button(
                "🚀 Backtest Çalıştır",
                key=f"btn_sniper_backtest_{symbol}_{timeframe}",
                use_container_width=True,
            )
        
        if run_btn:
            try:
                from tezaver.sniper.sniper_backtest import run_sniper_backtest_for_symbol_timeframe
                
                with st.spinner("Sniper Backtest çalışıyor..."):
                    result = run_sniper_backtest_for_symbol_timeframe(symbol, timeframe, float(risk))
                
                # Özet metrikler
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("💰 Sermaye", f"{result['capital_start']:.0f} → {result['capital_end']:.0f}")
                c2.metric("📈 PnL %", f"{result['pnl_pct']:+.2f}%")
                c3.metric("🏆 Win Rate", f"{result['win_rate']:.1f}%")
                c4.metric("📉 Max DD", f"{result['max_drawdown_pct']:.1f}%")
                
                st.caption(
                    f"Entries (toplam): {result['total_entries']} | "
                    f"Entries (seçilen): {result['selected_entries']} | "
                    f"Trades: {result['trade_count']}"
                )
                
                # Ham result JSON
                with st.expander("🧬 Ham Sonuç JSON", expanded=False):
                    st.json(result)
                    
            except FileNotFoundError as e:
                st.error(f"Dosya bulunamadı: {e}")
            except ValueError as e:
                st.error(f"Değer hatası: {e}")
            except Exception as e:
                st.error(f"Beklenmeyen hata: {e}")
    
    # =========== SNIPER VS SILVER A/B ===========
    render_sniper_vs_silver_section(symbol, timeframe)


def render_sniper_vs_silver_section(symbol: str, timeframe: str):
    """Sniper vs Silver A/B comparison UI."""
    from pathlib import Path
    
    with st.expander("⚖️ Sniper vs Silver A/B Karşılaştırma", expanded=False):
        st.caption(
            "Silver 15m full replay ile Sniper stratejisini aynı sermaye & risk altında karşılaştırır. "
            "Hangi strateji daha iyi?"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            ab_risk = st.slider(
                "Risk / Trade (A/B için)",
                min_value=0.01,
                max_value=1.0,
                value=1.0,
                step=0.01,
                key=f"sniper_vs_silver_risk_{symbol}_{timeframe}",
            )
        with col2:
            ab_tight = st.slider(
                "Silver Tightness",
                min_value=0,
                max_value=100,
                value=50,
                step=5,
                key=f"sniper_vs_silver_tight_{symbol}_{timeframe}",
            )
        
        run_ab = st.button(
            "⚖️ Sniper vs Silver A/B Çalıştır",
            key=f"btn_sniper_vs_silver_{symbol}_{timeframe}",
            use_container_width=True,
        )
        
        if run_ab:
            try:
                from tezaver.sniper.sniper_vs_silver_report import run_sniper_vs_silver_report
                
                with st.spinner("Sniper vs Silver A/B çalışıyor..."):
                    ab_result = run_sniper_vs_silver_report(
                        symbol=symbol,
                        timeframe=timeframe,
                        risk_per_trade=float(ab_risk),
                        tightness=int(ab_tight),
                        mode="experiment",
                    )
                
                silver = ab_result["silver"]
                sniper = ab_result["sniper"]
                delta = ab_result["delta"]
                
                col_s, col_sn = st.columns(2)
                
                with col_s:
                    st.markdown("### 🥈 Silver 15m")
                    st.metric(
                        "💰 100 → X",
                        f"{silver['capital_start']:.0f} → {silver['capital_end']:.1f}",
                        f"{silver['pnl_pct']:+.2f}%",
                    )
                    m1, m2 = st.columns(2)
                    m1.metric("🏆 Win Rate", f"{silver['win_rate']:.1f}%")
                    m2.metric("📉 Max DD", f"{silver['max_drawdown_pct']:.1f}%")
                    st.caption(f"Trades: {silver['trade_count']}")
                
                with col_sn:
                    st.markdown("### 🎯 Sniper v1")
                    st.metric(
                        "💰 100 → X",
                        f"{sniper['capital_start']:.0f} → {sniper['capital_end']:.1f}",
                        f"{sniper['pnl_pct']:+.2f}%",
                    )
                    m1, m2 = st.columns(2)
                    m1.metric("🏆 Win Rate", f"{sniper['win_rate']:.1f}%")
                    m2.metric("📉 Max DD", f"{sniper['max_drawdown_pct']:.1f}%")
                    st.caption(
                        f"Trades: {sniper['trade_count']} "
                        f"(Entries: {sniper['extra']['entries_selected']}/{sniper['extra']['entries_total']})"
                    )
                
                st.divider()
                
                # Delta summary
                st.markdown("**Δ Sniper - Silver:**")
                d1, d2, d3 = st.columns(3)
                d1.metric("Δ PnL", f"{delta['pnl_pct_diff']:+.2f}%")
                d2.metric("Δ Capital", f"{delta['capital_end_diff']:+.1f}")
                d3.metric("Δ Max DD", f"{delta['max_dd_diff']:+.1f}%")
                
                # Ham result JSON
                with st.expander("🧬 Ham A/B JSON", expanded=False):
                    st.json(ab_result)
                    
            except FileNotFoundError as e:
                st.error(f"Dosya bulunamadı: {e}")
            except Exception as e:
                st.error(f"Hata: {e}")


def render_event_list(symbol: str, tf: str, events: list, repo: SniperAnnotationRepository):
    """Render the left column with event list and filters."""
    
    st.markdown("### 📋 Rally Listesi")
    
    # Status filter
    status_filter = st.radio(
        "Durum filtresi",
        options=["HEPSİ", "PENDING", "APPROVED", "REJECTED", "REVIEWED"],
        horizontal=True,
        key="sniper_status_filter"
    )
    
    # Grade filter with counts
    total_events = len(events)
    grade_counts = {
        "Diamond": sum(1 for e in events if e.grade == "Diamond"),
        "Gold": sum(1 for e in events if e.grade == "Gold"),
        "Silver": sum(1 for e in events if e.grade == "Silver"),
        "Bronze": sum(1 for e in events if e.grade == "Bronze"),
    }
    
    grade_options = [
        f"HEPSİ ({total_events}/{total_events})",
        f"Diamond ({grade_counts['Diamond']}/{total_events})",
        f"Gold ({grade_counts['Gold']}/{total_events})",
        f"Silver ({grade_counts['Silver']}/{total_events})",
        f"Bronze ({grade_counts['Bronze']}/{total_events})",
    ]
    
    grade_filter_raw = st.radio(
        "Grade filtresi",
        options=grade_options,
        horizontal=True,
        key="sniper_grade_filter"
    )
    
    # Extract grade from selection
    grade_filter = grade_filter_raw.split(" (")[0]  # "Diamond (5/80)" → "Diamond"
    
    # Load all annotations for this symbol/tf
    all_annotations = repo.load_all(symbol, tf)
    ann_by_event = {str(a.event_id): a for a in all_annotations}
    
    # Filter events
    filtered_events = []
    for event in events:
        # Grade filter
        if grade_filter != "HEPSİ" and event.grade != grade_filter:
            continue
        
        # Status filter
        ann = ann_by_event.get(event.event_id)
        # Use getattr for backward compatibility with cached class
        event_status = getattr(ann, 'status', 'PENDING') if ann else "NEW"
        
        if status_filter != "HEPSİ":
            if status_filter == "PENDING" and event_status not in ["PENDING", "NEW"]:
                continue
            elif status_filter != "PENDING" and event_status != status_filter:
                continue
        
        filtered_events.append((event, ann, event_status))
    
    st.caption(f"Gösterilen: **{len(filtered_events)}** / {len(events)} rally")
    
    # Build selectbox options
    if not filtered_events:
        st.info("Filtre sonucu boş.")
        return
    
    # Session state for current selection
    if "sniper_current_event_id" not in st.session_state:
        st.session_state["sniper_current_event_id"] = filtered_events[0][0].event_id
    
    def format_event_option(event: SilverEventSummary, ann: Optional[SniperAnnotation], status: str):
        grade_icons = {"Diamond": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        status_icons = {"NEW": "🆕", "PENDING": "⏳", "REVIEWED": "👀", "APPROVED": "✅", "REJECTED": "❌"}
        
        grade_icon = grade_icons.get(event.grade, "❓")
        status_icon = status_icons.get(status, "❓")
        
        time_short = event.event_time[:16] if len(event.event_time) > 16 else event.event_time
        
        return f"{status_icon} {grade_icon} %{event.gain_pct:.1f} | {time_short}"
    
    options = [format_event_option(e, a, s) for e, a, s in filtered_events]
    event_ids = [e.event_id for e, _, _ in filtered_events]
    
    # Find current selection index
    try:
        current_idx = event_ids.index(st.session_state["sniper_current_event_id"])
    except ValueError:
        current_idx = 0
        st.session_state["sniper_current_event_id"] = event_ids[0]
    
    selected_option = st.selectbox(
        "Rally seç:",
        options=options,
        index=current_idx,
        key="sniper_event_select"
    )
    
    # Update session state based on selection
    selected_idx = options.index(selected_option)
    st.session_state["sniper_current_event_id"] = event_ids[selected_idx]
    
    # Next PENDING button
    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("⏭️ Sonraki PENDING", use_container_width=True):
            next_ann = repo.get_next_pending(symbol, tf, st.session_state["sniper_current_event_id"])
            if next_ann:
                st.session_state["sniper_current_event_id"] = next_ann.event_id
                st.rerun()
            else:
                st.info("PENDING kayıt yok.")
    
    with col_btn2:
        pending_count = len(repo.list_by_status(symbol, tf, "PENDING"))
        st.metric("PENDING", pending_count)


def render_chart_and_editor(symbol: str, tf: str, events: list, repo: SniperAnnotationRepository):
    """Render the right column with chart and annotation editor."""
    
    current_event_id = st.session_state.get("sniper_current_event_id")
    
    if not current_event_id:
        st.info("Soldan bir rally seçerek başlayın.")
        return
    
    # Find the event
    event = next((e for e in events if e.event_id == current_event_id), None)
    
    if not event:
        st.error("Event bulunamadı.")
        return
    
    # Load existing annotation
    current_ann = repo.get_one(symbol, tf, current_event_id)
    
    # Header
    grade_icons = {"Diamond": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
    st.markdown(f"### {grade_icons.get(event.grade, '❓')} Rally: %{event.gain_pct:.2f}")
    
    # Chart and editor in sub-columns
    chart_col, editor_col = st.columns([2, 1])
    
    with editor_col:
        st.markdown("#### 🛠️ Annotation Editor")
        
        # Metrics
        m1, m2 = st.columns(2)
        m1.metric("Kazanç", f"%{event.gain_pct:.2f}")
        m2.metric("Süre", f"{event.bars_to_peak} bar")
        
        st.divider()
        
        # Entry offset slider
        st.markdown("**📍 Giriş Noktası**")
        entry_offset = st.slider(
            "Entry bar offset",
            min_value=-5,
            max_value=max(30, event.bars_to_peak + 10),
            value=current_ann.entry_bar_offset if current_ann else 0,
            help="Rally başlangıcına göre giriş barının ofseti",
            key="sniper_entry_offset"
        )
        
        exit_offset = st.slider(
            "Exit bar offset",
            min_value=0,
            max_value=max(50, event.bars_to_peak + 20),
            value=current_ann.exit_bar_offset if (current_ann and current_ann.exit_bar_offset) else 0,
            help="0 = Kullanma",
            key="sniper_exit_offset"
        )
        
        st.divider()
        
        # Status & Label
        st.markdown("**📊 Durum & Etiket**")
        
        status_options = ["PENDING", "REVIEWED", "APPROVED", "REJECTED"]
        status_labels = {
            "PENDING": "⏳ PENDING – Beklemede",
            "REVIEWED": "👁 REVIEWED – İncelendi",
            "APPROVED": "✅ APPROVED – Onaylandı",
            "REJECTED": "❌ REJECTED – Reddedildi",
        }
        current_status = getattr(current_ann, 'status', 'PENDING') if current_ann else "PENDING"
        status_idx = status_options.index(current_status) if current_status in status_options else 0
        
        status = st.selectbox(
            "Durum",
            options=status_options,
            index=status_idx,
            format_func=lambda x: status_labels.get(x, x),
            key="sniper_status"
        )
        
        label_options = ["UNCERTAIN", "GOOD", "BAD"]
        label_labels = {
            "UNCERTAIN": "❓ UNCERTAIN – Belirsiz",
            "GOOD": "👍 GOOD – İyi giriş",
            "BAD": "👎 BAD – Kötü giriş",
        }
        current_label = getattr(current_ann, 'label', 'UNCERTAIN') if current_ann else "UNCERTAIN"
        label_idx = label_options.index(current_label) if current_label in label_options else 0
        
        label = st.selectbox(
            "Etiket",
            options=label_options,
            index=label_idx,
            format_func=lambda x: label_labels.get(x, x),
            key="sniper_label"
        )
        
        st.divider()
        
        # Tags
        st.markdown("**🏷️ Etiketler**")
        tag_options = ["RSI Div", "Support", "Breakout", "Volume", "MACD Cross", "Wick", "EMA Touch"]
        current_tags = current_ann.tags if (current_ann and current_ann.tags) else []
        tags = st.multiselect("Tags", tag_options, default=current_tags, key="sniper_tags")
        
        # Note
        st.markdown("**📝 Not**")
        note = st.text_area(
            "Not",
            value=current_ann.note if current_ann else "",
            height=80,
            key="sniper_note"
        )
        
        # Save button
        if st.button("💾 Kaydet", type="primary", use_container_width=True):
            repo.append(
                symbol=symbol,
                timeframe=tf,
                event_id=current_event_id,
                entry_bar_offset=entry_offset,
                note=note,
                exit_bar_offset=exit_offset if exit_offset > 0 else None,
                tags=tags,
                status=status,
                label=label,
            )
            st.success("✅ Sniper kaydı güncellendi!")
            st.rerun()
    
    with chart_col:
        # Render chart
        event_time = event.event_time
        
        if event_time:
            render_sniper_studio_chart(
                symbol=symbol,
                timeframe=tf,
                event_time=event_time,
                bars_to_peak=event.bars_to_peak,
                entry_offset=entry_offset,
                exit_offset=exit_offset if exit_offset > 0 else None
            )
        else:
            st.error("Event zaman verisi yok.")
