"""
Matrix Panel UI Card Components
ActionCard, StatCard, and landing helpers.
"""
import streamlit as st
from typing import List, Dict, Optional, Callable


def render_stat_card(title: str, value: str, delta: str = None, color: str = "blue"):
    """
    Render a statistics card with value and optional delta.
    """
    delta_html = ""
    if delta:
        delta_color = "#4CAF50" if delta.startswith("+") else "#f44336" if delta.startswith("-") else "#888"
        delta_html = f'<span style="color:{delta_color}; font-size:12px;">{delta}</span>'
    
    colors = {
        "blue": "#1976D2",
        "green": "#4CAF50",
        "orange": "#FF9800",
        "red": "#f44336",
        "purple": "#9C27B0",
        "gray": "#607D8B"
    }
    bg_color = colors.get(color, colors["blue"])
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {bg_color}22, {bg_color}11);
        border-left: 4px solid {bg_color};
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 12px;
    ">
        <div style="color: #888; font-size: 12px; margin-bottom: 4px;">{title}</div>
        <div style="font-size: 28px; font-weight: bold; color: #fff;">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_action_card(
    title: str,
    icon: str,
    description: str,
    action_key: str,
    badge: str = None,
    disabled: bool = False,
    color: str = "blue"
) -> bool:
    """
    Render an action card with icon, title, description.
    Returns True if clicked.
    """
    colors = {
        "blue": "#1976D2",
        "green": "#4CAF50",
        "orange": "#FF9800",
        "red": "#f44336",
        "purple": "#9C27B0",
        "gray": "#607D8B"
    }
    bg_color = colors.get(color, colors["blue"])
    
    opacity = "0.5" if disabled else "1"
    cursor = "not-allowed" if disabled else "pointer"
    
    badge_html = ""
    if badge:
        badge_color = "#f44336" if badge == "NEW" else "#FF9800" if badge == "BETA" else "#4CAF50"
        badge_html = f'<span style="background:{badge_color}; color:#fff; padding:2px 6px; border-radius:4px; font-size:10px; margin-left:8px;">{badge}</span>'
    
    locked_html = ""
    if disabled:
        locked_html = '<span style="color:#f44336; font-size:20px; position:absolute; right:12px; top:12px;">🔒</span>'
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {bg_color}15, {bg_color}08);
        border: 1px solid {bg_color}33;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        opacity: {opacity};
        cursor: {cursor};
        position: relative;
        transition: all 0.2s ease;
    " class="action-card">
        {locked_html}
        <div style="font-size: 32px; margin-bottom: 8px;">{icon}</div>
        <div style="font-size: 16px; font-weight: bold; color: #fff; margin-bottom: 4px;">
            {title}{badge_html}
        </div>
        <div style="font-size: 12px; color: #888;">{description}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not disabled:
        return st.button(f"→ {title}", key=action_key, use_container_width=True)
    return False


def render_folder_header(title: str, subtitle: str, icon: str = ""):
    """Render folder landing header."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 20px;
        border: 1px solid #333;
    ">
        <div style="font-size: 36px; margin-bottom: 8px;">{icon}</div>
        <h1 style="margin: 0; color: #fff;">{title}</h1>
        <p style="color: #888; margin: 8px 0 0 0;">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def render_quick_actions(actions: List[Dict]):
    """
    Render quick action button strip.
    actions: [{"label": "New", "icon": "➕", "key": "new_btn"}, ...]
    """
    cols = st.columns(len(actions))
    results = {}
    
    for i, action in enumerate(actions):
        with cols[i]:
            icon = action.get("icon", "")
            label = action.get("label", "Action")
            key = action.get("key", f"qa_{i}")
            disabled = action.get("disabled", False)
            
            if st.button(f"{icon} {label}", key=key, disabled=disabled, use_container_width=True):
                results[key] = True
    
    return results


def render_safe_mode_banner(is_active: bool = False, reason: str = ""):
    """Render SAFE_MODE warning banner if active."""
    if is_active:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f4433644, #f4433622);
            border: 1px solid #f44336;
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
        ">
            <span style="font-size: 24px; margin-right: 12px;">⚠️</span>
            <div>
                <div style="font-weight: bold; color: #f44336;">SAFE MODE AKTİF</div>
                <div style="font-size: 12px; color: #888;">{reason or "Yeni order açma kapalı"}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_locked_banner(message: str = "Bu özellik henüz aktif değil"):
    """Render locked/coming soon banner."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #60606044, #60606022);
        border: 1px solid #606060;
        padding: 40px;
        border-radius: 12px;
        text-align: center;
        margin: 40px 0;
    ">
        <div style="font-size: 48px; margin-bottom: 16px;">🔒</div>
        <div style="font-size: 18px; font-weight: bold; color: #888;">LOCKED</div>
        <div style="font-size: 14px; color: #666; margin-top: 8px;">{message}</div>
    </div>
    """, unsafe_allow_html=True)


def render_card_grid(cards: List[Dict], columns: int = 3):
    """
    Render a grid of action cards.
    cards: [{"title", "icon", "description", "key", "badge", "disabled", "color"}, ...]
    """
    clicked = None
    rows = [cards[i:i+columns] for i in range(0, len(cards), columns)]
    
    for row in rows:
        cols = st.columns(columns)
        for i, card in enumerate(row):
            with cols[i]:
                if render_action_card(
                    title=card.get("title", ""),
                    icon=card.get("icon", "📄"),
                    description=card.get("description", ""),
                    action_key=card.get("key", f"card_{i}"),
                    badge=card.get("badge"),
                    disabled=card.get("disabled", False),
                    color=card.get("color", "blue")
                ):
                    clicked = card.get("key")
    
    return clicked
