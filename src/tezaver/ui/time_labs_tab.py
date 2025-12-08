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
    
    # Handle No Data
    if events_df is None:
        st.info(f"Bu coin için '{timeframe}' zaman diliminde henüz Time-Labs rallisi bulunamadı.")
        if timeframe == "15m":
             st.markdown(f"**Taramayı çalıştırmak için:**")
             st.code(f"python src/tezaver/rally/run_fast15_rally_scan.py --symbol {symbol}", language="bash")
        else:
            st.markdown(f"**Taramayı çalıştırmak için:**")
            st.code(f"python src/tezaver/rally/run_time_labs_scan.py --tf {timeframe} --symbol {symbol}", language="bash")
        return

    # ===== SECTION 1: Summary + Filters =====
    col_summary, col_filter = st.columns([2, 3])
    
    with col_summary:
        st.markdown("#### Özet")
        if summary_data and "summary_tr" in summary_data:
            st.markdown(summary_data["summary_tr"])
        else:
            st.info("Özet bilgisi henüz mevcut değil.")
            
    with col_filter:
        st.markdown("#### Filtreler")
        
        # Bucket Filter
        bucket_labels = {
            "all": "Tüm Kovalar",
            "5p_10p": "%5 – %10",
            "10p_20p": "%10 – %20",
            "20p_30p": "%20 – %30",
            "30p_plus": "%30+"
        }
        
        c1, c2 = st.columns(2)
        with c1:
            selected_bucket = st.selectbox(
                "Yükseliş Kovası",
                options=list(bucket_labels.keys()),
                format_func=lambda k: bucket_labels[k],
                key=f"tl_bucket_{timeframe}_{symbol}"
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
        
        if selected_bucket != "all":
            filtered_df = filtered_df[filtered_df["rally_bucket"] == selected_bucket]
            
        if "quality_score" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["quality_score"] >= min_quality]
            
        # Metrics line
        if not filtered_df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Olay Sayısı", len(filtered_df))
            
            avg_gain = filtered_df["future_max_gain_pct"].mean() * 100
            m2.metric("Ort. Getiri", f"{avg_gain:.1f}%")
            
            if "quality_score" in filtered_df.columns:
                avg_qual = filtered_df["quality_score"].mean()
                m3.metric("Ort. Kalite", f"{avg_qual:.1f}")
        else:
            st.warning("Seçilen filtrelerde olay bulunamadı.")
            return

    # ===== SECTION 2: Chart & Snapshot =====
    st.markdown("---")
    st.markdown("### 📊 Rally Analizi")
    
    col_chart, col_snap = st.columns([3, 2])
    
    with col_snap:
        st.markdown("#### Bir Olay Seçin")
        
        # Sort by most recent
        display_df = filtered_df.sort_values("event_time", ascending=False).head(50)
        
        # Build selectbox labels
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
            
            gain = row['future_max_gain_pct'] * 100
            qual = int(row.get('quality_score', 0))
            shape = row.get('rally_shape', 'unk')
            
            label = f"{event_dt.strftime('%Y-%m-%d %H:%M')} | +{gain:.1f}% | Q:{qual} ({shape})"
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
        
        # Snapshot Card
        st.markdown(f"""
        **Olay:** {format_date_tr(sel_dt)}
        **Getiri:** %{sel_event['future_max_gain_pct']*100:.1f} ({sel_event['bars_to_peak']} bar)
        **Kalite:** {safe_fmt(sel_event.get('quality_score', 0), 0)} / 100
        **Şekil:** {sel_event.get('rally_shape', '-')}
        """)
        
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
