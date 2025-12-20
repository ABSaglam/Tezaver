"""
Time-Labs Tab - UI for 1h and 4h rally scanner results.

Generic component that renders a Time-Labs analysis tab for a given timeframe.
"""

import streamlit as st
import pandas as pd
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger
from tezaver.core.config import format_date_tr, to_turkey_time
from tezaver.ui.chart_area import render_rally_event_chart
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


@st.cache_data(ttl=600)
def load_time_labs_rallies(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Load Time-Labs events parquet."""
    try:
        if timeframe == "15m":
            path = coin_cell_paths.get_fast15_rallies_path(symbol)
        else:
            path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
    except TypeError:
        logger.error(f"Invalid path helper signature for {timeframe}")
        return None
        
    if not path.exists():
        logger.debug(f"Time-Labs {timeframe} events not found for {symbol}")
        return None
        
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return None
        return df
    except Exception as e:
        logger.error(f"Error loading Time-Labs {timeframe} events: {e}")
        return None


@st.cache_data(ttl=600)
def load_time_labs_summary(symbol: str, timeframe: str) -> Optional[Dict]:
    """Load Time-Labs summary JSON."""
    try:
        if timeframe == "15m":
            path = coin_cell_paths.get_fast15_rallies_summary_path(symbol)
        else:
            path = coin_cell_paths.get_time_labs_rallies_summary_path(symbol, timeframe)
    except TypeError:
        return None
        
    if not path.exists():
        return None
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading Time-Labs {timeframe} summary: {e}")
        return None


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


def render_time_labs_tab(symbol: str, timeframe: str):
    """
    Render a Time-Labs tab for the given timeframe.
    
    Args:
        symbol: Coin symbol
        timeframe: "15m", "1h" or "4h"
    """
    # Header
    if timeframe == "1h":
        tf_label = "1 Saat"
    elif timeframe == "4h":
        tf_label = "4 Saat"
    else:
        tf_label = "15 Dakika"
        
    st.markdown(f"### ⏱ {tf_label} Time-Labs (Rally Laboratuvarı)")
    
    # Load Data
    events_df = load_time_labs_rallies(symbol, timeframe)
    summary_data = load_time_labs_summary(symbol, timeframe)
    
    if events_df is None:
        st.info(f"Bu coin için '{timeframe}' zaman diliminde henüz Time-Labs rallisi bulunamadı.")
        if timeframe == "15m":
             st.markdown(f"**Taramayı çalıştırmak için:**")
             st.code(f"python src/tezaver/rally/run_fast15_rally_scan.py --symbol {symbol}", language="bash")
        else:
            st.markdown(f"**Taramayı çalıştırmak için:**")
            st.code(f"python src/tezaver/rally/run_time_labs_scan.py --tf {timeframe} --symbol {symbol}", language="bash")
        return
    
    # Consolidate overlapping rallies FIRST
    events_df = consolidate_overlapping_rallies(events_df, timeframe)
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
                return "🎗️ Weak"
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
                key=f"tl_badge_{timeframe}_{symbol}"
            )
            
        # Quality Filter
        with c2:
            min_quality = st.slider(
                "Min. Kalite Puanı",
                0, 100, 0,
                key=f"tl_qual_{timeframe}_{symbol}"
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
             # Handle timestamps
            ts = row['event_time']
            if isinstance(ts, (int, float)) and ts > 1e10: 
                event_dt = pd.to_datetime(ts, unit='ms')
            else:
                event_dt = pd.to_datetime(ts)
            
            # Localize
            event_dt = to_turkey_time(event_dt)
            
            # Get values
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
            key=f"tl_sel_{timeframe}_{symbol}"
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
        
        with st.expander("Detaylı Metrikler (Multi-TF)", expanded=True):
            # Use Tabs for cleaner organization of detailed multi-tf data
            t15, t1h, t4h, t1d = st.tabs(["15dk", "1 Saat", "4 Saat", "1 Gün"])
            
            with t15:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_15m'))}")
                    st.markdown(f"**RSI EMA**: {safe_fmt(sel_event.get('rsi_ema_15m'))}")
                    st.markdown(f"**Hacim Rel**: {safe_fmt(sel_event.get('volume_rel_15m'))}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {sel_event.get('macd_phase_15m', '-')}")
                    st.markdown(f"**MACD Hist**: {safe_fmt(sel_event.get('macd_hist_15m'), 4)}")
                    st.markdown(f"**ATR %**: {safe_pct(sel_event.get('atr_pct_15m'))}")

            with t1h:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_1h'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(sel_event.get('trend_soul_1h'))}")
                    st.markdown(f"**Rejim**: {sel_event.get('regime_1h', '-')}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {sel_event.get('macd_phase_1h', '-')}")
                    st.markdown(f"**Hacim Rel**: {safe_fmt(sel_event.get('volume_rel_1h'))}")
                    st.markdown(f"**Risk**: {sel_event.get('risk_level_1h', '-')}")

            with t4h:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(sel_event.get('rsi_4h'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(sel_event.get('trend_soul_4h'))}")
                    st.markdown(f"**Rejim**: {sel_event.get('regime_4h', '-')}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {sel_event.get('macd_phase_4h', '-')}")
                    st.markdown(f"**MACD Hist**: {safe_fmt(sel_event.get('macd_hist_4h'), 4)}")
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
        render_rally_event_chart(
            symbol=symbol,
            timeframe=timeframe,
            event_time=sel_dt,
            bars_to_peak=int(sel_event['bars_to_peak'])
        )

    # ===== SECTION 3: Data Table =====
    st.markdown("---")
    st.markdown("### 📋 Detaylı Liste")
    
    # Prepare table columns
    out_df = filtered_df.sort_values("event_time", ascending=False).copy()
    
    # Columns config
    cols_map = {
        "event_time": "Zaman",
        "rally_bucket": "Kova",
        "future_max_gain_pct": "Getiri",
        "quality_score": "Kalite",
        "rally_shape": "Şekil",
        "bars_to_peak": "Süre (Bar)",
        "pre_peak_drawdown_pct": "Drawdown",
        f"rsi_{timeframe}": f"RSI ({timeframe})",
        f"volume_rel_{timeframe}": f"HacimRel ({timeframe})"
    }
    
    # Filter available columns
    avail_cols = [c for c in cols_map.keys() if c in out_df.columns]
    
    # Format
    display_tbl = out_df[avail_cols].rename(columns=cols_map)
    
    # Format shape with emoji
    if "Şekil" in display_tbl.columns:
        shape_emoji = {'clean': '✨', 'choppy': '🌊', 'weak': '💤', 'spike': '⚡', 'unknown': '❓'}
        display_tbl["Şekil"] = display_tbl["Şekil"].apply(lambda x: shape_emoji.get(str(x).lower(), '❓'))
    
    st.dataframe(
        display_tbl, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "Getiri": st.column_config.NumberColumn(format="%.1f%%"),
            "Drawdown": st.column_config.NumberColumn(format="%.1f%%"),
            "Zaman": st.column_config.DatetimeColumn(format="D MMM HH:mm"),
        }
    )
