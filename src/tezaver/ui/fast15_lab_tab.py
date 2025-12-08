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


def render_fast15_lab_tab(symbol: str):
    """
    Render the Fast15 Rally Scanner tab in Yükseliş Lab.
    
    Layout:
    - Top: Summary text + Bucket filter with metrics
    - Middle: Chart + Multi-TF snapshot card
    - Bottom: Event list table
    """
    st.markdown("### 15 Dakika Hızlı Yükselişler")
    
    # Load data
    events_df, summary_data = load_fast15_data(symbol)
    
    # Handle no data case
    if events_df is None:
        st.info("Bu coin için henüz Fast15 rallisi bulunamadı.")
        st.markdown("**Fast15 taramasını çalıştırmak için:**")
        st.code(f"python src/tezaver/rally/run_fast15_rally_scan.py --symbol {symbol}", language="bash")
        st.markdown("_Not: Bu özellik 15 dakikalık hızlı yükselişleri tespit eder ve lab/gözlem amaçlıdır._")
        return
    
    # ===== SECTION 1: Summary + Bucket Filter =====
    col_summary, col_filter = st.columns([2, 3])
    
    with col_summary:
        st.markdown("#### Özet")
        if summary_data and "summary_tr" in summary_data:
            st.markdown(summary_data["summary_tr"])
        else:
            st.info("Fast15 özet bilgisi henüz oluşturulmamış.")
    
    with col_filter:
        st.markdown("#### Yükseliş Kovası")
        
        bucket_labels = {
            "all": "Tüm Kovalar",
            "5p_10p": "%5 – %10",
            "10p_20p": "%10 – %20",
            "20p_30p": "%20 – %30",
            "30p_plus": "%30+"
        }
        
        selected_bucket_key = st.radio(
            "Filtre",
            options=list(bucket_labels.keys()),
            format_func=lambda k: bucket_labels[k],
            horizontal=True,
            label_visibility="collapsed",
            key=f"fast15_bucket_{symbol}"
        )
        
        # Filter events by bucket
        filtered_df = events_df.copy()
        if selected_bucket_key != "all":
            filtered_df = filtered_df[filtered_df["rally_bucket"] == selected_bucket_key]
        
        if filtered_df.empty:
            st.warning(f"Seçili kovada ({bucket_labels[selected_bucket_key]}) Fast15 rally bulunamadı.")
        else:
            # Show metrics
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Olay Sayısı", len(filtered_df))
            with c2:
                avg_gain = filtered_df["future_max_gain_pct"].mean() * 100
                st.metric("Ort. Max Getiri", f"{avg_gain:.1f}%")
            with c3:
                avg_bars = filtered_df["bars_to_peak"].mean()
                st.metric("Ort. Tepeye Mum", f"{avg_bars:.1f}")
    
    # Early return if no events in selected bucket
    if filtered_df.empty:
        return
    
    # ===== SECTION 2: Chart + Snapshot =====
    st.markdown("---")
    st.markdown("### Tipik Örnekler ve Grafik")
    
    col_chart, col_snapshot = st.columns([3, 2])
    
    with col_snapshot:
        st.markdown("#### Bir Olay Seçin")
        
        # Sort and limit to last 50 events
        display_df = filtered_df.sort_values("event_time", ascending=False).head(50)
        
        # Create labels for selectbox
        event_labels = []
        for _, row in display_df.iterrows():
            # Handle potential ms timestamps
            ts = row['event_time']
            if isinstance(ts, (int, float)) and ts > 1e10: # Likely ms
                event_dt = pd.to_datetime(ts, unit='ms')
            else:
                event_dt = pd.to_datetime(ts)
            
            # Adjust to UTC+3
            from tezaver.core.config import to_turkey_time
            event_dt = to_turkey_time(event_dt)
                
            gain_pct = row['future_max_gain_pct'] * 100
            bars = row['bars_to_peak']
            label = f"{event_dt.strftime('%Y-%m-%d %H:%M')} – {gain_pct:.1f}% ({bars} mum)"
            event_labels.append(label)
        
        selected_index = st.selectbox(
            "15m Fast15 Olayları",
            options=list(range(len(display_df))),
            format_func=lambda idx: event_labels[idx],
            label_visibility="collapsed",
            key=f"fast15_event_{symbol}"
        )
        
        selected_event = display_df.iloc[selected_index]
        
        # Multi-TF snapshot card
        # Replaced with Standardized Multi-TF Tabs as per user request
        with st.expander("Detaylı Metrikler (Multi-TF)", expanded=True):
            t15, t1h, t4h, t1d = st.tabs(["15dk", "1 Saat", "4 Saat", "1 Gün"])
            
            with t15:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(selected_event.get('rsi_15m'))}")
                    st.markdown(f"**RSI EMA**: {safe_fmt(selected_event.get('rsi_ema_15m'))}")
                    st.markdown(f"**Hacim Rel**: {safe_fmt(selected_event.get('volume_rel_15m'))}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {selected_event.get('macd_phase_15m', '-')}")
                    st.markdown(f"**MACD Hist**: {safe_fmt(selected_event.get('macd_hist_15m'), 4)}")
                    st.markdown(f"**ATR %**: {safe_pct(selected_event.get('atr_pct_15m'))}")
            
            with t1h:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(selected_event.get('rsi_1h'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(selected_event.get('trend_soul_1h'))}")
                    st.markdown(f"**Rejim**: {selected_event.get('regime_1h', '-')}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {selected_event.get('macd_phase_1h', '-')}")
                    st.markdown(f"**Hacim Rel**: {safe_fmt(selected_event.get('volume_rel_1h'))}")
                    st.markdown(f"**Risk**: {selected_event.get('risk_level_1h', '-')}")
            
            with t4h:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(selected_event.get('rsi_4h'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(selected_event.get('trend_soul_4h'))}")
                    st.markdown(f"**Rejim**: {selected_event.get('regime_4h', '-')}")
                with c2:
                    st.markdown(f"**MACD Fazı**: {selected_event.get('macd_phase_4h', '-')}")
                    st.markdown(f"**MACD Hist**: {safe_fmt(selected_event.get('macd_hist_4h'), 4)}")
                    st.markdown(f"**Risk**: {selected_event.get('risk_level_4h', '-')}")
            
            with t1d:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**RSI**: {safe_fmt(selected_event.get('rsi_1d'))}")
                    st.markdown(f"**Trend Soul**: {safe_fmt(selected_event.get('trend_soul_1d'))}")
                with c2:
                    st.markdown(f"**Rejim**: {selected_event.get('regime_1d', '-')}")
                    st.markdown(f"**Risk**: {selected_event.get('risk_level_1d', '-')}")
    
    with col_chart:

        # Import chart function
        try:
            from tezaver.ui.chart_area import render_rally_event_chart
            
            render_rally_event_chart(
                symbol=symbol,
                timeframe="15m",
                event_time=event_dt,
                bars_to_peak=int(selected_event['bars_to_peak']),
            )
        except ImportError:
            st.warning("Grafik modülü henüz yüklenemedi.")
        except Exception as e:
            st.error(f"Grafik oluşturulurken hata: {e}")
            
    # ===== SECTION 3: Event List Table =====
    st.markdown("---")
    st.markdown("### Olay Listesi")
    
    # Prepare table columns
    table_df = filtered_df.copy()
    table_df = table_df.sort_values("event_time", ascending=False)
    
    # Convert gain to percentage
    table_df["future_max_gain_pct"] = table_df["future_max_gain_pct"] * 100.0
    
    # Select columns to display
    display_cols = [
        "event_time",
        "rally_bucket",
        "future_max_gain_pct",
        "bars_to_peak",
        "rsi_15m",
        "rsi_ema_15m",
        "macd_phase_15m",
        "trend_soul_1h",
        "trend_soul_4h",
        "trend_soul_1d",
    ]
    
    # Filter to available columns
    available_cols = [c for c in display_cols if c in table_df.columns]
    
    if not available_cols:
        st.warning("Olay verilerinde gösterilecek kolon bulunamadı.")
        return
    
    table_df_display = table_df[available_cols].copy()
    
    # Rename columns to Turkish
    column_rename = {
        "event_time": "Zaman",
        "rally_bucket": "Kova",
        "future_max_gain_pct": "Max Getiri (%)",
        "bars_to_peak": "Tepeye Mum",
        "rsi_15m": "RSI (15dk)",
        "rsi_ema_15m": "RSI EMA (15dk)",
        "macd_phase_15m": "MACD Fazı (15dk)",
        "trend_soul_1h": "TrendSoul (1sa)",
        "trend_soul_4h": "TrendSoul (4sa)",
        "trend_soul_1d": "TrendSoul (1gn)",
    }
    
    table_df_display = table_df_display.rename(columns=column_rename)
    
    st.dataframe(
        table_df_display,
        use_container_width=True,
        hide_index=True,
    )
    
    # Footer note
    st.caption(f"Toplam {len(filtered_df)} olay gösteriliyor ({bucket_labels[selected_bucket_key]})")
