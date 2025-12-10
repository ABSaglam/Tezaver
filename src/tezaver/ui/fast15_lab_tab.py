"""
Fast15 Lab Tab - UI for 15-minute rapid rally analysis.

Displays Fast15 Rally Scanner results in the Yükseliş Lab section.
"""

import streamlit as st
import pandas as pd
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger
from tezaver.rally.rally_narrative_engine import analyze_scenario, SCENARIO_DEFINITIONS

logger = get_logger(__name__)


def safe_fmt(value, decimals: int = 2) -> str:
    """Format float value or return '-' if NaN/None."""
    if value is None or pd.isna(value):
        return "-"
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return "-"


def safe_pct(value, decimals: int = 1) -> str:
    """Format percentage value or return '-' if NaN/None."""
    if value is None or pd.isna(value):
        return "-"
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "-"


def load_fast15_data(symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[dict]]:
    """
    Load Fast15 events and summary for a symbol.
    
    Returns:
        Tuple of (events_df, summary_data)
        - events_df: DataFrame with rally events, or None if not found
        - summary_data: Dict with summary stats, or None if not found
    """
    # Load events parquet
    events_path = coin_cell_paths.get_fast15_rallies_path(symbol)
    events_df = None
    
    if not events_path.exists():
        logger.debug(f"Fast15 events not found for {symbol}: {events_path}")
    else:
        try:
            events_df = pd.read_parquet(events_path)
            if events_df.empty:
                logger.info(f"Fast15 events file is empty for {symbol}")
                events_df = None
            else:
                logger.info(f"Loaded {len(events_df)} Fast15 events for {symbol}")
        except Exception as e:
            logger.error(f"Error loading Fast15 events for {symbol}: {e}")
            events_df = None
    
    # Load summary JSON
    summary_path = coin_cell_paths.get_fast15_rallies_summary_path(symbol)
    summary_data = None
    
    if not summary_path.exists():
        logger.debug(f"Fast15 summary not found for {symbol}: {summary_path}")
    else:
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
            logger.info(f"Loaded Fast15 summary for {symbol}")
        except Exception as e:
            logger.error(f"Error loading Fast15 summary for {symbol}: {e}")
            summary_data = None
    
    return events_df, summary_data


def consolidate_overlapping_rallies(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Consolidate overlapping rallies - keep only best (highest gain)."""
    if df.empty:
        return df
    
    # Calculate bar duration
    if timeframe == "4h":
        bar_delta = pd.Timedelta(hours=4)
    elif timeframe == "1h":
        bar_delta = pd.Timedelta(hours=1)
    else:
        bar_delta = pd.Timedelta(minutes=15)
    
    # Calculate end_time
    df = df.copy()
    df['end_time'] = df['event_time'] + df['bars_to_peak'].astype(int) * bar_delta
    
    # Sort by gain descending
    df = df.sort_values('future_max_gain_pct', ascending=False).reset_index(drop=True)
    
    # Greedy consolidation
    kept_indices = []
    kept_ranges = []
    
    for idx, row in df.iterrows():
        start = row['event_time']
        end = row['end_time']
        
        overlaps = False
        for kept_start, kept_end in kept_ranges:
            if start < kept_end and kept_start < end:
                overlaps = True
                break
        
        if not overlaps:
            kept_indices.append(idx)
            kept_ranges.append((start, end))
    
    result = df.loc[kept_indices].drop(columns=['end_time'], errors='ignore')
    result = result.sort_values('event_time').reset_index(drop=True)
    return result


def render_fast15_lab_tab(symbol: str) -> None:
    """Renders Fast15 Rally Scanner tab - Standard Layout matching Time Labs."""
    
    from tezaver.core.config import format_date_tr, to_turkey_time
    from tezaver.ui.chart_area import render_rally_event_chart
    
    # Determine label
    tf_label = "15 Dakika"
    timeframe = "15m"
        
    st.markdown(f"### ⏱ {tf_label} Time-Labs (Rally Laboratuvarı)")
    
    # =================================================================
    # LOAD DATA
    # =================================================================
    events_df, summary_data = load_fast15_data(symbol)
    
    if events_df is None or events_df.empty:
        st.info(f"Bu coin için '{timeframe}' zaman diliminde henüz rally bulunamadı.")
        st.markdown(f"**Taramayı çalıştırmak için:**")
        st.code(f"python src/tezaver/rally/run_fast15_rally_scan.py --symbol {symbol}", language="bash")
        return
    
    # Consolidate overlapping rallies
    events_df = consolidate_overlapping_rallies(events_df, timeframe)
    events_df['event_time'] = pd.to_datetime(events_df['event_time'])
    rally_count_after_consolidation = len(events_df)
    
    if events_df.empty:
        st.warning("Rally bulunamadı.")
        return

    # ===== SECTION 1: Summary + Filters =====
    col_summary, col_filter = st.columns([2, 3])
    
    with col_summary:
        st.markdown("#### 📊 Özet")
        c1, c2, c3 = st.columns(3)
        c1.metric("Rally", len(events_df))
        if 'future_max_gain_pct' in events_df.columns and len(events_df) > 0:
            avg_gain = events_df['future_max_gain_pct'].mean() * 100
            c2.metric("Ort. Kazanç", f"%{avg_gain:.1f}")
        if 'quality_score' in events_df.columns:
            avg_qual = events_df['quality_score'].mean()
            c3.metric("Ort. Kalite", f"{avg_qual:.0f}")
            
    with col_filter:
        st.markdown("#### Filtreler")
        
        # Assign grades FIRST (before building options)
        if 'rally_grade' not in events_df.columns:
            def get_grade(pct):
                if pct >= 0.30: return "💎 Diamond"
                if pct >= 0.20: return "🥇 Gold"
                if pct >= 0.10: return "🥈 Silver"
                if pct >= 0.05: return "🥉 Bronze"
                return "�️ Weak"
            events_df['rally_grade'] = events_df['future_max_gain_pct'].apply(get_grade)
        
        # Build badge options with stats
        badge_options = ["♾️ Hepsi"]
        badge_labels = {
            "♾️ Hepsi": f"♾️ Hepsi ({len(events_df)})"
        }
        
        for badge in ["💎 Diamond", "🥇 Gold", "🥈 Silver", "🥉 Bronze"]:
            subset = events_df[events_df['rally_grade'] == badge]
            count = len(subset)
            if count > 0:
                avg_gain = subset['future_max_gain_pct'].mean() * 100
                avg_qual = subset['quality_score'].mean() if 'quality_score' in subset.columns else 0
                badge_options.append(badge)
                badge_labels[badge] = f"{badge} ({count}) %{avg_gain:.0f} Q:{avg_qual:.0f}"
            else:
                badge_options.append(badge)
                badge_labels[badge] = f"{badge} (0)"
        
        # Badge (Grade) Filter
        c1, c2 = st.columns(2)
        with c1:
            badge_filter = st.selectbox(
                "🏆 Rally Sınıfı",
                options=badge_options,
                format_func=lambda x: badge_labels.get(x, x),
                key=f"f15_badge_{symbol}"
            )
            
        # Quality Filter
        with c2:
            min_quality = st.slider(
                "Min. Kalite Puanı",
                0, 100, 0,
                key=f"f15_qual_{symbol}"
            )
            
    # Apply Filters
    filtered_df = events_df.copy()
    
    if badge_filter != "♾️ Hepsi":
        filtered_df = filtered_df[filtered_df["rally_grade"] == badge_filter]
        
    if "quality_score" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["quality_score"] >= min_quality]
    
    if filtered_df.empty:
        st.warning("Seçilen filtrelerde olay bulunamadı.")
        return

    # ===== SECTION 2: Chart & Snapshot =====
    st.markdown("---")
    
    col_chart, col_snap = st.columns([3, 2])
    
    with col_snap:
        st.markdown("#### Bir Olay Seçin")
        
        # Sort by most recent
        display_df = filtered_df.sort_values("event_time", ascending=False).head(50)
        
        # Build selectbox labels with standard format
        event_opts = []
        for i, row in display_df.iterrows():
            ts = row['event_time']
            if isinstance(ts, (int, float)) and ts > 1e10: 
                event_dt = pd.to_datetime(ts, unit='ms')
            else:
                event_dt = pd.to_datetime(ts)
            
            event_dt = to_turkey_time(event_dt)
            
            gain = row['future_max_gain_pct'] * 100
            qual = int(row.get('quality_score', 0))
            shape = str(row.get('rally_shape', 'unknown')).capitalize()
            
            # Get badge icon
            if gain >= 30: badge = "💎"
            elif gain >= 20: badge = "🥇"
            elif gain >= 10: badge = "🥈"
            elif gain >= 5: badge = "🥉"
            else: badge = "🎗️"
            
            label = f"{badge} | {event_dt.strftime('%d %b %Y %H:%M')} | %{gain:.1f} ({int(row.get('bars_to_peak', 0))} bar) | Q:{qual} | {shape}"
            event_opts.append(label)
            
        selected_idx = st.selectbox(
            "Listeden Seç:",
            options=range(len(display_df)),
            format_func=lambda i: event_opts[i],
            label_visibility="collapsed",
            key=f"f15_sel_{symbol}"
        )
        
        sel_event = display_df.iloc[selected_idx]
        sel_dt = pd.to_datetime(sel_event['event_time'])
        
        # Get badge and shape for display
        gain_pct = sel_event['future_max_gain_pct'] * 100
        if gain_pct >= 30: badge = "💎 Diamond"
        elif gain_pct >= 20: badge = "🥇 Gold"
        elif gain_pct >= 10: badge = "🥈 Silver"
        elif gain_pct >= 5: badge = "🥉 Bronze"
        else: badge = "🎗️ Weak"
        
        shape_val = str(sel_event.get('rally_shape', 'Unknown')).capitalize()
        quality_val = safe_fmt(sel_event.get('quality_score', 0), 0)
        sel_dt_tz = to_turkey_time(sel_dt)
        
        # Snapshot Card - Compact horizontal format
        st.markdown(f"#### {badge}")
        st.markdown(f"**Kazanç:** %{gain_pct:.1f} | **Süre:** {int(sel_event['bars_to_peak'])} bar | **Tarih:** {sel_dt_tz.strftime('%d %b %Y %H:%M')}")
        st.markdown(f"**Kalite:** {quality_val}/100 | **Şekil:** {shape_val}")
        
        # Scenario/Narrative Display
        scenario_id = analyze_scenario(sel_event)
        scenario_def = SCENARIO_DEFINITIONS.get(scenario_id, {})
        scenario_label = scenario_def.get('label', 'Belirsiz')
        scenario_risk = scenario_def.get('risk', 'Medium')
        scenario_desc = scenario_def.get('desc', '')
        
        # Risk badge colors
        risk_colors = {'Low': '🟢', 'Medium': '🟡', 'High': '🔴'}
        risk_badge = risk_colors.get(scenario_risk, '⚪')
        
        st.markdown(f"**Senaryo:** {scenario_label} | **Risk:** {risk_badge} {scenario_risk}")
        
        with st.expander("📖 Hikaye", expanded=False):
            st.markdown(f"**{scenario_label}**")
            st.info(scenario_desc)
        
        with st.expander("Detaylı Metrikler (Multi-TF)", expanded=False):
            t15, t1h, t4h, t1d = st.tabs(["15dk", "1 Saat", "4 Saat", "1 Gün"])
            
            with t15:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_15m'))}")
                    st.markdown(f"**RSI EMA**: {safe_fmt(sel_event.get('rsi_ema_15m'))}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {sel_event.get('macd_phase_15m', '-')}")
                    st.markdown(f"**Hacim Rel**: {safe_fmt(sel_event.get('volume_rel_15m'))}")
            
            with t1h:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_1h'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(sel_event.get('trend_soul_1h'))}")
                with c2:
                    st.markdown(f"**Rejim**: {sel_event.get('regime_1h', '-')}")
                    st.markdown(f"**Risk**: {sel_event.get('risk_level_1h', '-')}")
            
            with t4h:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_4h'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(sel_event.get('trend_soul_4h'))}")
                with c2:
                    st.markdown(f"**Rejim**: {sel_event.get('regime_4h', '-')}")
                    st.markdown(f"**Risk**: {sel_event.get('risk_level_4h', '-')}")
            
            with t1d:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_1d'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(sel_event.get('trend_soul_1d'))}")
                with c2:
                    st.markdown(f"**Rejim**: {sel_event.get('regime_1d', '-')}")
                    st.markdown(f"**Risk**: {sel_event.get('risk_level_1d', '-')}")
        
        # Info notes
        st.caption(f"📊 {rally_count_after_consolidation} rally (overlap temizlendi)")
    
    with col_chart:
        # Chart for selected event
        sel_dt_tz = to_turkey_time(sel_dt)
        
        
        try:
            render_rally_event_chart(
                symbol=symbol,
                timeframe="15m",
                event_time=sel_dt_tz,
                bars_to_peak=int(sel_event['bars_to_peak']),
            )
        except Exception as e:
            st.error(f"Grafik oluşturulurken hata: {e}")

    # ===== SECTION 3: Detailed List =====
    st.markdown("---")
    st.markdown("### 📋 Olay Listesi")
    
    table_df = filtered_df.copy()
    table_df = table_df.sort_values("event_time", ascending=False)
    
    # Convert gain to percentage
    table_df["future_max_gain_pct"] = table_df["future_max_gain_pct"] * 100.0
    
    # Select columns to display
    display_cols = ["rally_grade", "event_time", "future_max_gain_pct", "bars_to_peak"]
    
    if "quality_score" in table_df.columns:
        display_cols.append("quality_score")
    if "rally_shape" in table_df.columns:
        display_cols.append("rally_shape")
        
    table_display = table_df[[c for c in display_cols if c in table_df.columns]].copy()
    
    # Rename for display
    col_map = {
        "rally_grade": "Sınıf",
        "event_time": "Zaman",
        "future_max_gain_pct": "Kazanç %",
        "bars_to_peak": "Süre (Bar)",
        "quality_score": "Kalite",
        "rally_shape": "Şekil"
    }
    table_display = table_display.rename(columns=col_map)
    
    # Format values
    table_display["Kazanç %"] = table_display["Kazanç %"].apply(lambda x: f"%{x:.1f}")
    if "Kalite" in table_display.columns:
        table_display["Kalite"] = table_display["Kalite"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "-")
    if "Şekil" in table_display.columns:
        table_display["Şekil"] = table_display["Şekil"].apply(lambda x: str(x).capitalize() if pd.notna(x) else "Unknown")
    
    st.dataframe(
        table_display,
        use_container_width=True,
        hide_index=True,
        height=400
    )
