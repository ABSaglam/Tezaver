"""
Rally Quality Tab - Quality Analysis UI
========================================

Displays Rally Quality analysis showing rally shapes (Clean/Spike/Choppy)
and quality scores for each timeframe.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def load_rally_quality_data(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Load rally events with quality metrics.
    
    Args:
        symbol: Coin symbol
        timeframe: Timeframe ('15m', '1h', '4h')
    
    Returns:
        DataFrame with rally events including quality columns or None
    """
    if timeframe == "15m":
        rallies_path = coin_cell_paths.get_fast15_rallies_path(symbol)
    else:
        rallies_path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
    
    if not rallies_path.exists():
        return None
    
    try:
        df = pd.read_parquet(rallies_path)
        # Check if quality columns exist
        quality_cols = ['rally_shape', 'quality_score', 'efficiency', 'retention_3', 'retention_10']
        has_quality = all(col in df.columns for col in quality_cols[:2])  # At least shape and score
        
        if not has_quality:
            logger.warning(f"Rally quality columns missing for {symbol} {timeframe}")
            return None
        
        return df
    except Exception as e:
        logger.error(f"Error loading rally quality data for {symbol} {timeframe}: {e}")
        return None


def get_shape_emoji(shape: str) -> str:
    """Get emoji for rally shape."""
    shape_map = {
        "clean": "✨",
        "spike": "⚡",
        "choppy": "🌊",
        "weak": "💤"
    }
    return shape_map.get(shape.lower() if isinstance(shape, str) else "", "❓")


def get_shape_color(shape: str) -> str:
    """Get color for rally shape."""
    color_map = {
        "clean": "#00aa00",
        "spike": "#ffaa00",
        "choppy": "#ff6600",
        "weak": "#888888"
    }
    return color_map.get(shape.lower() if isinstance(shape, str) else "", "#888888")


def render_rally_quality_tab(symbol: str) -> None:
    """
    Render Rally Quality tab showing shape and quality analysis.
    
    Args:
        symbol: Coin symbol (e.g., 'BTCUSDT')
    """
    st.markdown("### 🎯 Rally Quality - Kalite Analizi")
    
    st.markdown("""
    **Rally Quality Sistemi**, her rally'nin şeklini ve kalitesini analiz eder:
    - **✨ Clean**: Temiz, doğrusal yükseliş
    - **⚡ Spike**: Ani iğne, hızlı düşen
    - **🌊 Choppy**: Dalgalı, düzensiz
    - **💤 Weak**: Zayıf momentum
    """)
    
    # Timeframe selection
    timeframe_tabs = st.tabs(["⚡ 15 Dakika", "⏱ 1 Saat", "⏱ 4 Saat"])
    timeframe_map = {"⚡ 15 Dakika": "15m", "⏱ 1 Saat": "1h", "⏱ 4 Saat": "4h"}
    
    for idx, (label, tf) in enumerate(timeframe_map.items()):
        with timeframe_tabs[idx]:
            render_quality_timeframe(symbol, tf)


def render_quality_timeframe(symbol: str, timeframe: str) -> None:
    """Render quality analysis for a specific timeframe."""
    
    df = load_rally_quality_data(symbol, timeframe)
    
    if df is None or df.empty:
        st.info(f"🔍 {symbol} için {timeframe} rally kalite verisi bulunamadı.")
        st.markdown("""
        **Veri oluşturmak için:**
        1. Sidebar → System Scans → Rally taraması çalıştırın
        2. Rally Quality Engine otomatik olarak kalite skorları ekleyecektir
        """)
        return
    
    # Summary Statistics
    st.markdown(f"#### 📊 Özet ({len(df)} Rally)")
    
    # Shape Distribution
    if 'rally_shape' in df.columns:
        shape_counts = df['rally_shape'].value_counts()
        
        cols = st.columns(len(shape_counts))
        for idx, (shape, count) in enumerate(shape_counts.items()):
            with cols[idx]:
                emoji = get_shape_emoji(shape)
                pct = (count / len(df)) * 100
                st.metric(
                    f"{emoji} {shape.capitalize()}",
                    f"{count}",
                    f"{pct:.1f}%"
                )
    
    st.markdown("---")
    
    # Quality Score Distribution
    if 'quality_score' in df.columns:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_quality = df['quality_score'].mean()
            st.metric("Ortalama Kalite", f"{avg_quality:.1f}/100")
        
        with col2:
            high_quality = (df['quality_score'] >= 70).sum()
            st.metric("Yüksek Kalite (≥70)", f"{high_quality}")
        
        with col3:
            low_quality = (df['quality_score'] < 40).sum()
            st.metric("Düşük Kalite (\u003c40)", f"{low_quality}")
    
    # Detailed Table
    st.markdown("#### 📋 Detaylı Rally Listesi")
    
    # Filter by shape
    if 'rally_shape' in df.columns:
        unique_shapes = df['rally_shape'].unique().tolist()
        shape_filter = st.multiselect(
            "Şekil Filtresi",
            options=unique_shapes,
            default=unique_shapes
        )
        
        df_filtered = df[df['rally_shape'].isin(shape_filter)].copy()
    else:
        df_filtered = df.copy()
    
    # Display columns
    display_cols = []
    if 'event_time' in df_filtered.columns:
        display_cols.append('event_time')
    if 'rally_shape' in df_filtered.columns:
        display_cols.append('rally_shape')
    if 'quality_score' in df_filtered.columns:
        display_cols.append('quality_score')
    if 'future_max_gain_pct' in df_filtered.columns:
        display_cols.append('future_max_gain_pct')
    if 'bars_to_peak' in df_filtered.columns:
        display_cols.append('bars_to_peak')
    if 'efficiency' in df_filtered.columns:
        display_cols.append('efficiency')
    if 'retention_10' in df_filtered.columns:
        display_cols.append('retention_10')
    
    if display_cols:
        # Format the dataframe for display
        df_display = df_filtered[display_cols].copy()
        
        # Rename columns to Turkish
        column_names = {
            'event_time': 'Olay Zamanı',
            'rally_shape': 'Şekil',
            'quality_score': 'Kalite',
            'future_max_gain_pct': 'Kazanç %',
            'bars_to_peak': 'Süre (Bar)',
            'efficiency': 'Verimlilik',
            'retention_10': 'Retention (10)'
        }
        df_display = df_display.rename(columns=column_names)
        
        # Format percentages
        for col in ['Kazanç %', 'Verimlilik', 'Retention (10)']:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "-")
        
        # Format quality score
        if 'Kalite' in df_display.columns:
            df_display['Kalite'] = df_display['Kalite'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
        
        st.dataframe(
            df_display.sort_values('Olay Zamanı', ascending=False) if 'Olay Zamanı' in df_display.columns else df_display,
            use_container_width=True,
            height=400
        )
    else:
        st.warning("Görüntülenecek kalite metriği bulunamadı.")
