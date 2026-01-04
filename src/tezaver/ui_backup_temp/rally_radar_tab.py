"""
Rally Radar Tab - Environment Status UI
========================================

Displays Rally Radar analysis results showing market environment status
(HOT/COLD/NEUTRAL/CHAOTIC) for each timeframe.
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from typing import Optional, Dict, Any

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def load_rally_radar_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Load Rally Radar profile for a coin.
    
    Returns:
        Dictionary with radar analysis or None if not found
    """
    profile_dir = coin_cell_paths.get_coin_profile_dir(symbol)
    radar_file = profile_dir / "rally_radar_profile.json"
    
    if not radar_file.exists():
        return None
    
    try:
        with open(radar_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading rally radar for {symbol}: {e}")
        return None


def get_status_emoji(status: str) -> str:
    """Get emoji for environment status."""
    status_map = {
        "HOT": "🔥",
        "NEUTRAL": "🌤️",
        "COLD": "❄️",
        "CHAOTIC": "🌀",
        "NO_DATA": "❓"
    }
    return status_map.get(status, "⚪")


def get_status_color(status: str) -> str:
    """Get color for environment status."""
    color_map = {
        "HOT": "#ff4444",
        "NEUTRAL": "#ffaa00",
        "COLD": "#4444ff",
        "CHAOTIC": "#aa00ff",
        "NO_DATA": "#888888"
    }
    return color_map.get(status, "#888888")


def render_rally_radar_tab(symbol: str) -> None:
    """
    Render Rally Radar tab showing environment analysis.
    
    Args:
        symbol: Coin symbol (e.g., 'BTCUSDT')
    """
    st.markdown("### 📡 Rally Radar - Piyasa Ortamı Analizi")
    
    radar_data = load_rally_radar_data(symbol)
    
    if not radar_data:
        st.info(f"🔍 {symbol} için Rally Radar verisi bulunamadı.")
        st.markdown("""
        **Rally Radar nedir?**
        - Piyasa ortamını analiz eder (HOT/NEUTRAL/COLD/CHAOTIC)
        - Rally yoğunluğu, kalite ve netlik skorları hesaplar
        - Trend uyum durumunu değerlendirir
        
        **Veri oluşturmak için:**
        Sidebar → System Scans → "Rally Radar" taramasını çalıştırın.
        """)
        return
    
    # Overall Summary
    overall_status = radar_data.get("overall_status", "NO_DATA")
    overall_score = radar_data.get("overall_environment_score", 0)
    
    col1, col2, col3 = st.columns([1, 2, 2])
    
    with col1:
        emoji = get_status_emoji(overall_status)
        st.markdown(f"### {emoji}")
        st.metric("Genel Durum", overall_status)
    
    with col2:
        st.metric("Ortam Skoru", f"{overall_score:.1f}/100")
        st.progress(overall_score / 100)
    
    with col3:
        last_update = radar_data.get("scan_timestamp", "Bilinmiyor")
        st.caption(f"Son Güncelleme: {last_update}")
        flags = radar_data.get("flags", [])
        if flags:
            st.warning(f"⚠️ {', '.join(flags)}")
    
    st.markdown("---")
    
    # Timeframe Analysis
    st.markdown("#### 📊 Zaman Dilimi Analizi")
    
    timeframes_data = radar_data.get("timeframes", {})
    
    if timeframes_data:
        # Create tabs for each timeframe
        tf_keys = [tf for tf in ["15m", "1h", "4h"] if tf in timeframes_data]
        tf_labels = {"15m": "⚡ 15 Dakika", "1h": "⏱ 1 Saat", "4h": "⏱ 4 Saat"}
        
        tf_tabs = st.tabs([tf_labels.get(tf, tf) for tf in tf_keys])
        
        for idx, tf in enumerate(tf_keys):
            with tf_tabs[idx]:
                render_timeframe_radar(timeframes_data[tf], tf)
    else:
        st.warning("Zaman dilimi verileri bulunamadı.")


def render_timeframe_radar(tf_data: Dict[str, Any], timeframe: str) -> None:
    """Render radar analysis for a specific timeframe."""
    
    status = tf_data.get("status", "NO_DATA")
    score = tf_data.get("environment_score", 0)
    emoji = get_status_emoji(status)
    color = get_status_color(status)
    
    # Status Card
    st.markdown(f"""
    <div style="background-color: {color}22; border-left: 4px solid {color}; padding: 16px; border-radius: 4px; margin-bottom: 16px;">
        <h3 style="margin: 0; color: {color};">{emoji} {status}</h3>
        <p style="margin: 8px 0 0 0; color: #ffffff;">Ortam Skoru: {score:.1f}/100</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        event_count = tf_data.get("event_count", 0)
        st.metric("Rally Sayısı", event_count)
    
    with col2:
        clean_ratio = tf_data.get("clean_ratio", 0) * 100
        st.metric("Clean Rally", f"{clean_ratio:.1f}%")
    
    with col3:
        avg_quality = tf_data.get("avg_quality_score", 0)
        st.metric("Ort. Kalite", f"{avg_quality:.1f}")
    
    with col4:
        clarity = tf_data.get("clarity_index", 0)
        st.metric("Netlik İndeksi", f"{clarity:.2f}")
    
    # Detailed Stats
    with st.expander("📈 Detaylı İstatistikler"):
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("**Rally Kalitesi:**")
            st.write(f"• Spike Oranı: {tf_data.get('spike_ratio', 0)*100:.1f}%")
            st.write(f"• Ort. Kazanç: {tf_data.get('avg_future_max_gain_pct', 0)*100:.1f}%")
            st.write(f"• Ort. Retention: {tf_data.get('avg_retention_10_pct', 0)*100:.1f}%")
        
        with col_b:
            trend_context = tf_data.get("trend_context", {})
            st.markdown("**Trend Bağlamı:**")
            for key, value in trend_context.items():
                st.write(f"• {key}: {value}")
    
    # Flags
    flags = tf_data.get("flags", [])
    if flags:
        st.info(f"ℹ️ Notlar: {', '.join(flags)}")
