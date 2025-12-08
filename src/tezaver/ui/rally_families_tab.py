"""
Rally Families Tab - Family Clustering UI
==========================================

Displays Rally Families analysis showing clustered rally patterns
based on multi-timeframe technical characteristics.
"""

import streamlit as st
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def load_rally_families_data(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Load Rally Families data for a coin and timeframe.
    
    Args:
        symbol: Coin symbol
        timeframe: Timeframe ('15m', '1h', '4h', '1d')
    
    Returns:
        Dictionary with families data or None if not found
    """
    profile_dir = coin_cell_paths.get_coin_profile_dir(symbol)
    families_file = profile_dir / f"rally_families_{timeframe}.json"
    
    if not families_file.exists():
        return None
    
    try:
        with open(families_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading rally families for {symbol} {timeframe}: {e}")
        return None


def get_rally_class_label(rally_class: str) -> str:
    """Get Turkish label for rally class."""
    labels = {
        "rally_5p": "📊 %5+ Rally",
        "rally_10p": "📈 %10+ Rally",
        "rally_20p": "🚀 %20+ Rally"
    }
    return labels.get(rally_class, rally_class)


def get_trust_emoji(trust_score: float) -> str:
    """Get emoji based on trust score."""
    if trust_score >= 0.7:
        return "⭐"
    elif trust_score >= 0.5:
        return "✨"
    elif trust_score >= 0.3:
        return "💫"
    else:
        return "⚪"


def render_rally_families_tab(symbol: str) -> None:
    """
    Render Rally Families tab showing clustered rally patterns.
    
    Args:
        symbol: Coin symbol (e.g., 'BTCUSDT')
    """
    st.markdown("### 🧬 Rally Aileleri - Kümeleme Analizi")
    
    st.markdown("""
    **Rally Aileleri**, makine öğrenimi ile benzer özelliklere sahip rally'leri gruplar:
    - **Kümeleme:** K-Means algoritması ile benzer rally'ler aynı aileye atanır
    - **Özellikler:** RSI, MACD, hacim, trend gibi çok zaman-dilimli göstergeler
    - **Güven Skoru:** Her ailenin hedef kazançlara ulaşma olasılığı
    """)
    
    st.markdown("---")
    
    # Timeframe selection
    col1, col2 = st.columns(2)
    
    with col1:
        timeframe = st.selectbox(
            "Zaman Dilimi",
            options=["1h", "4h", "1d"],
            format_func=lambda x: {"1h": "⏱ 1 Saat", "4h": "⏱ 4 Saat", "1d": "📅 1 Gün"}.get(x, x),
            key=f"rf_tf_{symbol}"
        )
    
    families_data = load_rally_families_data(symbol, timeframe)
    
    if not families_data:
        st.info(f"🔍 {symbol} için {timeframe} rally aileleri verisi bulunamadı.")
        st.markdown("""
        **Veri oluşturmak için:**
        1. Sidebar → System Scans → "Rally Families" taramasını çalıştırın
        2. Rally Families Engine otomatik olarak aileleri oluşturacaktır
        """)
        return
    
    families = families_data.get("families", [])
    
    if not families:
        st.warning("Bu zaman dilimi için aile bulunamadı.")
        return
    
    # Summary metrics
    total_families = len(families)
    total_samples = sum(f.get("sample_count", 0) for f in families)
    avg_trust = sum(f.get("trust_score", 0) for f in families) / len(families) if families else 0
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Toplam Aile", total_families)
    with col_b:
        st.metric("Toplam Örnek", total_samples)
    with col_c:
        st.metric("Ort. Güven", f"{avg_trust:.2f}")
    
    st.markdown("---")
    
    # Group by rally class
    rally_classes = {}
    for family in families:
        rc = family.get("rally_class", "unknown")
        if rc not in rally_classes:
            rally_classes[rc] = []
        rally_classes[rc].append(family)
    
    # Display families by class
    for rally_class in ["rally_5p", "rally_10p", "rally_20p"]:
        if rally_class not in rally_classes:
            continue
        
        class_families = rally_classes[rally_class]
        class_label = get_rally_class_label(rally_class)
        
        with st.expander(f"{class_label} ({len(class_families)} Aile)", expanded=True):
            # Sort by trust score
            class_families.sort(key=lambda x: x.get("trust_score", 0), reverse=True)
            
            for family in class_families:
                render_family_card(family)


def render_family_card(family: Dict[str, Any]) -> None:
    """Render a single family card."""
    
    family_id = family.get("family_id", 0)
    sample_count = family.get("sample_count", 0)
    trust_score = family.get("trust_score", 0)
    
    emoji = get_trust_emoji(trust_score)
    trust_color = get_trust_color(trust_score)
    
    # Card header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {trust_color}22 0%, {trust_color}11 100%); 
                border-left: 4px solid {trust_color}; 
                padding: 16px; 
                border-radius: 8px; 
                margin-bottom: 12px;">
        <h4 style="margin: 0; color: {trust_color};">{emoji} Aile #{family_id}</h4>
        <p style="margin: 4px 0 0 0; color: #aaa;">Güven Skoru: {trust_score:.2%} • {sample_count} Örnek</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        hit_5p = family.get("hit_5p_rate", 0)
        st.metric("Hit %5", f"{hit_5p:.1%}")
    
    with col2:
        hit_10p = family.get("hit_10p_rate", 0)
        st.metric("Hit %10", f"{hit_10p:.1%}")
    
    with col3:
        hit_20p = family.get("hit_20p_rate", 0)
        st.metric("Hit %20", f"{hit_20p:.1%}")
    
    with col4:
        avg_gain = family.get("avg_future_max_gain_pct", 0)
        st.metric("Ort. Kazanç", f"{avg_gain:.1%}")
    
    # Additional stats in expander
    with st.expander("📊 Detaylı İstatistikler"):
        avg_loss = family.get("avg_future_max_loss_pct", 0)
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Performans:**")
            st.write(f"• Ortalama Kazanç: {avg_gain*100:.2f}%")
            st.write(f"• Ortalama Kayıp: {avg_loss*100:.2f}%")
            
            # Risk/Reward ratio
            if avg_loss != 0:
                rr_ratio = abs(avg_gain / avg_loss)
                st.write(f"• Risk/Reward: {rr_ratio:.2f}")
        
        with col_b:
            st.markdown("**Başarı Oranları:**")
            st.write(f"• %5 Hedef: {hit_5p*100:.1f}%")
            st.write(f"• %10 Hedef: {hit_10p*100:.1f}%")
            st.write(f"• %20 Hedef: {hit_20p*100:.1f}%")


def get_trust_color(trust_score: float) -> str:
    """Get color based on trust score."""
    if trust_score >= 0.7:
        return "#00ff88"
    elif trust_score >= 0.5:
        return "#ffaa00"
    elif trust_score >= 0.3:
        return "#ff6600"
    else:
        return "#888888"
