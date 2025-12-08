
import streamlit as st
import sys
import json
import subprocess
import time
import pandas as pd
import base64
from pathlib import Path
from datetime import datetime

# --- BOOTSTRAP ---
project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.core import state_store
from tezaver.core import system_state
from tezaver.wisdom.pattern_stats import get_coin_profile_dir
from tezaver.ui.subpages.system_dashboard import render_system_dashboard
from tezaver.ui.insight_tab import render_insight_tab
from tezaver.ui.fast15_lab_tab import render_fast15_lab_tab
from tezaver.ui.time_labs_tab import render_time_labs_tab
from tezaver.ui.rally_radar_tab import render_rally_radar_tab
from tezaver.ui.rally_quality_tab import render_rally_quality_tab
from tezaver.ui.rally_families_tab import render_rally_families_tab
from tezaver.ui.sim_lab_tab import render_sim_lab_tab
from tezaver.ui.risk_cards import render_risk_tab
from tezaver.ui.pattern_story_view import render_pattern_story_panel, PatternStoryKey
from tezaver.ui.explanation_cards import TRIGGER_LABELS_TR
import plotly.graph_objects as go

# --- HELPER FUNCTIONS ---

def get_img_base64(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return ""

def load_json_file(path: Path):
    if not path.exists(): return None
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return None

# --- SIDEBAR SECTIONS ---

def render_system_health_and_control_section():
    """Renders the System Pipeline Status in the Sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧬 Sistem Sağlığı")
    
    state = system_state.load_state()
    last_run = state.last_full_pipeline_run_at
    status = state.last_full_pipeline_status
    
    time_str = "--:--"
    if last_run:
        try:
            # Simple parsing, assuming ISO format
            dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
            time_str = dt.strftime("%H:%M")
        except: pass
        
    c1, c2 = st.sidebar.columns([2, 1])
    with c1:
        st.markdown(f"**Pipeline v2.1**")
        st.caption(f"✅ Hazır ({time_str})" if status == "success" else "⚠️ Beklemede")
    with c2:
        if st.button("🚀", help="Tam Tur Çalıştır"):
            st.session_state['current_page'] = 'system_dashboard'
            st.rerun()
            
    # Backup Button
    if st.sidebar.button("💾 Yedek Al", use_container_width=True, help="src, data ve library klasörlerini yedekler"):
        from tezaver.core.backup_engine import create_full_snapshot
        with st.spinner("Yedek alınıyor..."):
            success, msg = create_full_snapshot()
            if success:
                st.toast(msg, icon="✅")
                st.success(msg)
            else:
                st.error(msg)

def render_system_scans_section():
    """Renders the Offline Lab Maintenance & Scans section."""
    st.sidebar.markdown("### 🧪 Offline Lab Bakımı")
    
    # 1. Full Maintenance
    if st.sidebar.button("🚀 Full Lab Bakımı", use_container_width=True, help="Tüm taramaları ve analizleri (15 Dakika, TimeLabs, Radar) çalıştırır."):
        st.toast("Full Bakım Başlatıldı (Konsolu takip edin)...", icon="⏳")
        try:
            # Running as subprocess to not block UI thread excessively
            cmd = [sys.executable, "src/tezaver/offline/run_offline_maintenance.py", "--mode", "full", "--all-symbols"]
            env = dict(sys.modules['os'].environ)
            env["PYTHONPATH"] = "src"
            subprocess.Popen(cmd, env=env)
            st.sidebar.success("Bakım işlemi arka planda başlatıldı.")
        except Exception as e:
            st.error(f"Hata: {e}")

    st.sidebar.markdown("#### Hızlı Araçlar")
    
    # 2. Fast15 Scan
    if st.sidebar.button("⚡ 15 Dakika Tara", use_container_width=True):
        st.toast("15 Dakika Taraması Başlatıldı...", icon="⏳")
        try:
            cmd = [sys.executable, "src/tezaver/rally/run_fast15_rally_scan.py", "--all-symbols"]
            env = dict(sys.modules['os'].environ)
            env["PYTHONPATH"] = "src"
            subprocess.Popen(cmd, env=env)
            st.toast("İşlem başlatıldı.", icon="✅")
        except Exception as e:
            st.error(f"Hata: {e}")

    # 3. Time-Labs Buttons
    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.button("🕐 1H Lab", use_container_width=True):
            try:
                cmd = [sys.executable, "src/tezaver/rally/run_time_labs_scan.py", "--tf", "1h", "--all-symbols"]
                env = dict(sys.modules['os'].environ)
                env["PYTHONPATH"] = "src"
                subprocess.Popen(cmd, env=env)
                st.toast("1H Lab Başlatıldı", icon="✅")
            except Exception as e: st.error(str(e))
    with c2:
        if st.button("🕓 4H Lab", use_container_width=True):
            try:
                cmd = [sys.executable, "src/tezaver/rally/run_time_labs_scan.py", "--tf", "4h", "--all-symbols"]
                env = dict(sys.modules['os'].environ)
                env["PYTHONPATH"] = "src"
                subprocess.Popen(cmd, env=env)
                st.toast("4H Lab Başlatıldı", icon="✅")
            except Exception as e: st.error(str(e))
            
    # 4. Radar Update
    if st.sidebar.button("📡 Radar Güncelle", use_container_width=True):
        try:
            cmd = [sys.executable, "src/tezaver/rally/run_rally_radar_export.py"]
            env = dict(sys.modules['os'].environ)
            env["PYTHONPATH"] = "src"
            subprocess.Popen(cmd, env=env)
            st.toast("Radar güncellemesi başlatıldı.", icon="📡")
        except Exception as e: st.error(str(e))

# --- PAGE RENDERERS ---

def render_home_page():
    # Title removed as per user request (Header logo is sufficient)
    st.subheader("Offline Lab Kontrol Paneli")
    st.info("Sistem aktif. Sol menüden işlem seçebilirsiniz.")
    
    # Show basic stats if available
    try:
        state = system_state.load_state()
        c1, c2, c3 = st.columns(3)
        c1.metric("Son Full Bakım", state.last_offline_maintenance_run_at.split('T')[1][:5] if state.last_offline_maintenance_run_at else "-")
        c2.metric("Toplam Coin", len(state_store.load_coin_states() or []))
        c3.metric("Lab Durumu", "Aktif" if state.last_offline_maintenance_status != "failed" else "Hata")
    except:
        pass

def render_market_summary_page():
    st.title("📊 Piyasa Özeti")
    states = state_store.load_coin_states()
    if not states:
        st.warning("Veri yok.")
        return
    data = []
    for s in states:
        # Use getattr for safety, though model now has it
        price = getattr(s, 'last_price', 0.0)
        # Correct attribute is last_update (singular)
        updated = getattr(s, 'last_update', 'N/A')
        data.append({"Sembol": s.symbol, "Fiyat": price, "Güncelleme": updated})
    st.dataframe(pd.DataFrame(data), use_container_width=True)

def render_levels_tab(symbol: str):
    st.subheader("Trend Seviyeleri (Destek & Direnç)")
    profile_dir = get_coin_profile_dir(symbol)
    level_data = []
    for tf in ["1h", "4h", "1d"]:
        data = load_json_file(profile_dir / f"levels_{tf}.json")
        if data:
            for item in data:
                item['source_tf'] = tf
                level_data.append(item)
    
    if level_data:
        df = pd.DataFrame(level_data).sort_values("level_price", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Hesaplanmış seviye yok.")

# Consolidating render_patterns_tab into Wisdom/Sub-components if needed, 
# but keeping it here as a fallback or standalone tab if requested.
def render_patterns_tab(symbol: str):
    st.subheader("🌀 Patern Hikayeleri (Eski Görünüm)")
    # This might be redundant with Wisdom tab but user asked for "Patterns" tab in previous prompts.
    # In REV01 prompt, "Paternler" wasn't explicitly forbidden, but "Bilgelik" covers it.
    # We will keep it but maybe it simply points to Wisdom or renders the detailed view.
    # Let's keep the existing logic for detailed drill-down.
    
    export_path = get_coin_profile_dir(symbol) / "export_bulut.json"
    data = load_json_file(export_path)
    if not data:
        st.info("Veri yok.")
        return
    
    patterns_data = data.get("patterns", {})
    all_patterns = patterns_data.get("trustworthy", []) + patterns_data.get("betrayal", [])
    
    if not all_patterns:
        st.info("Patern yok.")
        return
        
    all_patterns.sort(key=lambda x: x.get('sample_count', 0), reverse=True)
    
    options = []
    pattern_map = {}
    
    for p in all_patterns:
        trig = p.get('trigger', 'unknown')
        tf = p.get('timeframe', '1h')
        trig_tr = TRIGGER_LABELS_TR.get(trig, trig)
        label = f"{trig_tr} ({tf}) - {p.get('sample_count')} Örnek"
        options.append(label)
        pattern_map[label] = p
        
    selected_label = st.selectbox("Patern Seçin:", options, key=f"pat_sel_old_{symbol}")
    if selected_label:
        p_data = pattern_map[selected_label]
        key = PatternStoryKey(
            symbol=symbol,
            trigger=p_data.get('trigger'),
            timeframe=p_data.get('timeframe')
        )
        st.markdown("---")
        render_pattern_story_panel(symbol, pattern_key=key, rally_family_key=None)


def render_bulut_export_tab(symbol: str):
    # Imports for Verbal Summary
    from tezaver.ui.explanation_cards import (
        load_coin_explanation_context,
        build_patterns_summary_tr,
        build_fast15_summary_tr,
        build_time_labs_summary_tr,
        build_strategy_affinity_summary_tr
    )
    
    st.subheader("☁️ Bulut Paketi")

    # ==== YENİ: Sözlü Özet Katmanı ====
    try:
        ctx = load_coin_explanation_context(symbol)
    except Exception as e:
        # logger is not available in local scope here unless imported, but st.error works
        # Assuming logger is global or we skip logging
        ctx = None

    st.markdown("### ☁️ Bulut Paketi – Sözlü Özet")

    if ctx is None:
        st.info("Bu coin için sözlü özet konteksi yüklenemedi.")
    else:
        pattern_text = build_patterns_summary_tr(ctx)
        fast15_text = build_fast15_summary_tr(ctx)
        time_labs_text = build_time_labs_summary_tr(ctx)
        strategy_text = build_strategy_affinity_summary_tr(ctx)

        # Check if we have ANY data
        if not any([pattern_text, fast15_text, time_labs_text, strategy_text]):
            st.info("Bu coin için henüz sözlü özet üretmek için yeterli veri yok.")
        else:
            if pattern_text:
                st.markdown("#### ⚡ Tetik ve Rally Özeti")
                st.markdown(pattern_text)

            if fast15_text:
                st.markdown("#### 🚀 15 Dakika Hızlı Yükseliş Özeti")
                st.markdown(fast15_text)

            if time_labs_text:
                st.markdown("#### 🕒 Time-Labs (1h / 4h) Özeti")
                st.markdown(time_labs_text)

            if strategy_text:
                st.markdown("#### 🧠 Strateji Uyum Özeti")
                st.markdown(strategy_text)

    st.markdown("---")

    # ==== ESKİ Export Metrikleri / İşlemleri ====
    st.markdown("#### 📤 Export İşlemleri")
    
    if st.button("Export Al (JSON Paketi)"):
        st.success("Tüm profil verileri data/coin_profiles altında güncellendi.")

# --- NEW UI COMPONENTS (Restored) ---

def render_coin_header(symbol: str):
    """
    Renders rich header with Price, 24h Change, Volume.
    Calculates 24h stats from history data on-the-fly.
    """
    # 1. Get base info
    states = state_store.load_coin_states()
    coin_state = state_store.find_coin_state(states, symbol)
    price = getattr(coin_state, 'last_price', 0.0)
    
    # 2. Calculate 24h stats from history
    change_pct = 0.0
    vol_24h = 0.0
    color = "gray"
    
    try:
        df = load_history_data(symbol, "1h")
        if df is not None and not df.empty and len(df) > 24:
            # Last candle
            current_close = df.iloc[-1]['close']
            # 24 hours ago
            prev_close = df.iloc[-25]['close']
            
            change_pct = ((current_close - prev_close) / prev_close) * 100
            
            # Volume 24h
            vol_24h = df.iloc[-24:]['volume'].sum()
            
            # Use real-time price if available and fresher, otherwise history
            # Actually history is usually the source of truth in offline mode.
            price = current_close
            
            if change_pct > 0: color = "green"
            elif change_pct < 0: color = "red"
    except Exception as e:
        pass

    # 3. Render
    c1, c2, c3, c4 = st.columns([1, 2, 2, 4])
    
    with c1:
        # Mini Logo
        logo_path = f"src/tezaver/ui/assets/coins/{symbol.replace('USDT','').lower()}.png"
        # We don't have these logos yet, use generic emoji or just symbol
        st.markdown(f"## {symbol}")
        
    with c2:
        st.metric("Fiyat", f"${price:,.2f}")
        
    with c3:
        st.metric("24h Değişim", f"{change_pct:+.2f}%", delta=f"{change_pct:.2f}%")
        
    with c4:
        st.metric("24h Hacim", f"{vol_24h:,.0f}")
        
    st.markdown("---")

from tezaver.ui.chart_area import load_history_data, render_universal_chart

def render_main_price_chart(symbol: str):
    """
    Renders the main price chart using Chart Area module.
    """
    # Timeframe selector for chart
    c_left, c_right = st.columns([1, 4])
    with c_left:
        tf = st.selectbox("Grafik", ["15m", "1h", "4h", "1d"], index=1, key=f"main_chart_tf_{symbol}")
    
    with c_right:
        st.caption(f"Tezaver Grafik ({tf})")

    # Render Chart using Universal Function
    try:
        render_universal_chart(
            symbol=symbol,
            timeframe=tf,
            event_time=None, # General view
            bars_to_peak=0
        )
    except Exception as e:
        st.error(f"Grafik hatası: {e}")

from tezaver.ui.time_labs_tab import render_time_labs_tab

def render_coin_detail_page(symbol: str):
    # HEADER
    render_coin_header(symbol)
    
    # TABS
    # Definition: Bilgelik, Rally, Sim Lab, Risk, Bulut, Paternler, Seviyeler, Ana Grafik
    tab_names = [
        "💡 Bilgelik", 
        "🚀 Rally", 
        "🧪 Sim Lab",
        "🛡️ Risk", 
        "☁️ Bulut Paketi",
        "🌀 Paternler",
        "📏 Seviyeler",
        "📊 Ana Grafik"
    ]
    
    tabs = st.tabs(tab_names)
    
    # 1. Bilgelik (Wisdom)
    with tabs[0]: 
        from tezaver.ui.explanation_cards import render_coin_explanation_cards
        render_coin_explanation_cards(symbol)

    # 2. Rally (Fast15 + Time-Labs + Radar + Quality + Families)
    with tabs[1]:
        sub_tabs = st.tabs(["⚡ 15 Dakika", "⏱ 1 Saat", "⏱ 4 Saat", "📡 Rally Radar", "🎯 Rally Quality", "🧬 Rally Aileleri"])
        
        with sub_tabs[0]:
            render_fast15_lab_tab(symbol)
        with sub_tabs[1]:
            render_time_labs_tab(symbol, "1h")
        with sub_tabs[2]:
            render_time_labs_tab(symbol, "4h")
        with sub_tabs[3]:
            render_rally_radar_tab(symbol)
        with sub_tabs[4]:
            render_rally_quality_tab(symbol)
        with sub_tabs[5]:
            render_rally_families_tab(symbol)
            
    # 3. Sim Lab (Backtest)
    with tabs[2]:
        render_sim_lab_tab(symbol)

    # 4. Risk
    with tabs[3]:
        render_risk_tab(symbol)
        
    # 5. Bulut Paketi (Export & Summary)
    with tabs[4]:
        render_bulut_export_tab(symbol)

    # 6. Paternler
    with tabs[5]:
        render_patterns_tab(symbol)

    # 7. Seviyeler
    with tabs[6]:
        render_levels_tab(symbol)

    # 8. Grafik (Main Chart)
    with tabs[7]:
        render_main_price_chart(symbol)


def render_cloud_mode():
    # Title removed
    st.sidebar.markdown("### Navigasyon")
    if st.sidebar.button("🏠 Ana Sayfa", use_container_width=True):
        st.rerun()
        
    st.sidebar.header("Sunucu Kontrol")
    st.info("Bulut modu geliştirme aşamasında.")

def render_matrix_mode():
    from tezaver.ui.subpages.cloud_page import render_cloud_page
    render_cloud_page()

# --- MODE SWITCHER & MAIN ---

import re

def get_processed_svg_base64(path: str, remove_animations: bool = False):
    """Reads SVG, optionally strips animations, returns base64 string."""
    try:
        if not Path(path).exists(): return ""
        
        # Read as text to manipulate
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if remove_animations:
             # Remove <animate ... /> and <animate ...></animate>
             # Simple regex for the self-closing or inline styles used in these SVGs.
             # The SVGs use <animate attributeName="..." ... />
             content = re.sub(r'<animate.*?>', '', content, flags=re.IGNORECASE)
             # Also optionally remove filters if they cause heavy glow look in inactive
             # content = re.sub(r'filter="url\(#glow\)"', '', content) 
             
        return base64.b64encode(content.encode("utf-8")).decode()
    except Exception:
        return ""

def render_mode_switcher():
    """Renders clickable HTML icons."""
    # Pre-calculate paths
    p_mac = "src/tezaver/ui/assets/tezaver_icon_mac.svg"
    p_cloud = "src/tezaver/ui/assets/tezaver_icon_cloud.svg"
    p_sim = "src/tezaver/ui/assets/tezaver_icon_sim.svg"

    current = st.session_state.get('system_mode', 'MAC')
    
    # Load Animated versions (for Active state)
    # We only REALLY need the animated one for the active state, 
    # and static for others, but let's load what we need.
    
    icon_mac_anim = get_processed_svg_base64(p_mac, remove_animations=False)
    icon_mac_static = get_processed_svg_base64(p_mac, remove_animations=True)
    
    icon_cloud_anim = get_processed_svg_base64(p_cloud, remove_animations=False)
    icon_cloud_static = get_processed_svg_base64(p_cloud, remove_animations=True)
    
    icon_sim_anim = get_processed_svg_base64(p_sim, remove_animations=False)
    icon_sim_static = get_processed_svg_base64(p_sim, remove_animations=True)
    
    style_active = "opacity: 1.0; filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.6)); transform: scale(1.1);"
    style_inactive = "opacity: 0.4; filter: grayscale(100%); transform: scale(0.85); transition: all 0.3s ease;"
    
    # helper selector
    def get_icon(mode_name, is_anim, is_static):
        return is_anim if current == mode_name else is_static

    html_code = f"""
    <div style="display: flex; justify-content: space-around; margin-bottom: 25px; align-items: center;">
        <a href="?mode=MAC" target="_self" style="text-decoration: none;">
            <img src="data:image/svg+xml;base64,{get_icon('MAC', icon_mac_anim, icon_mac_static)}" width="60" style="{style_active if current=='MAC' else style_inactive} transition: all 0.3s ease;">
        </a>
        <a href="?mode=CLOUD" target="_self" style="text-decoration: none;">
            <img src="data:image/svg+xml;base64,{get_icon('CLOUD', icon_cloud_anim, icon_cloud_static)}" width="60" style="{style_active if current=='CLOUD' else style_inactive} transition: all 0.3s ease;">
        </a>
        <a href="?mode=SIM" target="_self" style="text-decoration: none;">
            <img src="data:image/svg+xml;base64,{get_icon('SIM', icon_sim_anim, icon_sim_static)}" width="60" style="{style_active if current=='SIM' else style_inactive} transition: all 0.3s ease;">
        </a>
    </div>
    """
    st.sidebar.markdown(html_code, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Tezaver Restore V1", page_icon="🔮", layout="wide")
    
    # --- 1. Query Param Handler ---
    try:
        # Check for mode switch request
        if "mode" in st.query_params:
            new_mode = st.query_params["mode"]
            if new_mode in ["MAC", "CLOUD", "SIM"]:
                st.session_state['system_mode'] = new_mode
                
                # RESET NAVIGATION TO HOME
                st.session_state['nav_selection'] = "🏠 Ana Sayfa"
                if 'current_page' in st.session_state:
                    del st.session_state['current_page']
                if 'selected_coin' in st.session_state:
                    del st.session_state['selected_coin']
                    
            # Clear params to act as a one-time trigger
            st.query_params.clear()
            
    except Exception as e:
        pass
        
    # --- 2. Determine Colors ---
    current_mode = st.session_state.get('system_mode', 'MAC')
    
    if current_mode == 'MAC':
        border_bg = "linear-gradient(180deg, #4facfe 0%, #00f2fe 100%)"
    elif current_mode == 'CLOUD':
        # New Blue Theme
        border_bg = "linear-gradient(180deg, #2980B9 0%, #6DD5FA 100%)"
    elif current_mode == 'SIM':
        # New Red/Orange Theme (Swapped from Cloud)
        border_bg = "linear-gradient(180deg, #FF416C 0%, #FF4B2B 100%)"

    # --- 3. Logo Injection (Global Header) ---
    if current_mode == 'MAC':
        logo_file = "src/tezaver/ui/assets/tezaver_logo_mac.svg"
    elif current_mode == 'CLOUD':
        logo_file = "src/tezaver/ui/assets/tezaver_logo_cloud.svg"
    else:
        logo_file = "src/tezaver/ui/assets/tezaver_logo_sim.svg"

    # Convert to Base64 for CSS Injection
    logo_b64 = get_img_base64(logo_file)

    # --- 4. CSS Injection ---
    # We place the logo in the CENTER of the Header for a premium look
    st.markdown(f"""
        <style>
            /* Sidebar tweaks */
            [data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
            [data-testid="stSidebar"]::after {{
                content: ""; position: absolute; top: 0; right: 0; width: 5px; height: 100%;
                background: {border_bg}; z-index: 999;
            }}
            .block-container {{ padding-top: 6rem; }}
            
            /* GLOBAL HEADER LOGO INJECTION */
            [data-testid="stHeader"] {{
                background-image: url("data:image/svg+xml;base64,{logo_b64}");
                background-repeat: no-repeat;
                background-position: center center;
                background-size: auto 90%; 
                height: 5.0rem; 
                background-color: transparent !important; /* Remove background color */
            }}
            
            /* Optional: Hide standard decoration if it interferes */
            [data-testid="stDecoration"] {{
                display: none;
            }}
        </style>
    """, unsafe_allow_html=True)
    
    render_mode_switcher()
    
    # --- 2. Determine Colors ---
    current_mode = st.session_state.get('system_mode', 'MAC')
    
    # SYSTEM MODE ROUTING
    if current_mode == 'MAC':
        with st.sidebar:
            # st.header("🔬 Laboratuvar") REMOVED
            
            # --- NAVIGATION BUTTONS (Replacing Radio) ---
            # Default state
            if 'nav_selection' not in st.session_state:
                st.session_state['nav_selection'] = "🏠 Ana Sayfa"
            
            nav_options = [
                "🏠 Ana Sayfa", 
                "📊 Piyasa Özeti", 
                "👁️ Insight Panel", 
                "💾 Veri Merkezi", 
                "⚙️ Sistem Paneli"
            ]
            
            for option in nav_options:
                # Active button is Primary, others Secondary
                is_active = (st.session_state['nav_selection'] == option)
                if st.button(option, key=f"nav_{option}", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state['nav_selection'] = option
                    # Reset coin detail view when main nav changes
                    if 'current_page' in st.session_state: 
                        del st.session_state['current_page']
                    st.rerun()
            
            st.markdown("---")
            
            # Coin Selector
            states = state_store.load_coin_states()
            if states:
                symbols = [s.symbol for s in states]
                idx = 0
                if 'selected_coin' in st.session_state and st.session_state['selected_coin'] in symbols:
                    idx = symbols.index(st.session_state['selected_coin'])
                
                # Label is hidden as per user request ("Coin İncele" removed)
                sel_coin = st.selectbox("Coin İncele", symbols, index=idx, key="sb_coin_selector", label_visibility="collapsed")
                
                # Logic: Only redirect if user explicitly changes coin (not on init/reset)
                previous_coin = st.session_state.get('selected_coin')
                
                if sel_coin != previous_coin:
                    st.session_state['selected_coin'] = sel_coin
                    # Only redirect if we had a previous selection (active session)
                    # If previous was None (just reset/started), stay on Home.
                    if previous_coin is not None:
                        st.session_state['current_page'] = 'coin_detail'
                        st.rerun()
                
                if st.button("🔍 Detaya Git", use_container_width=True):
                    st.session_state['current_page'] = 'coin_detail'
                    st.rerun()
            else:
                st.warning("Coin verisi yok.")

            # Cleaned up as per user request (Moved to System Panel)
            pass

        # 3. Main Content Router
        # Check if we are in Detail View or Main Nav View
        current_nav = st.session_state.get('nav_selection', "🏠 Ana Sayfa")
        
        # Priority: Coin Detail View overrides Nav if explicitly set
        if st.session_state.get('current_page') == 'coin_detail' and st.session_state.get('selected_coin'):
             render_coin_detail_page(st.session_state['selected_coin'])
             if st.button("⬅️ Geri Dön (Ana Menü)"):
                 st.session_state['current_page'] = 'home' # Exit detail mode
                 st.rerun()
        else:
            # Main Navigation Routing
            if current_nav == "🏠 Ana Sayfa": render_home_page()
            elif current_nav == "📊 Piyasa Özeti": render_market_summary_page()
            elif current_nav == "👁️ Insight Panel": render_insight_tab()
            elif current_nav == "💾 Veri Merkezi": render_data_health_page()
            elif current_nav == "⚙️ Sistem Paneli": 
                from tezaver.ui.subpages.system_dashboard import render_system_dashboard
                render_system_dashboard()
        
    elif current_mode == 'CLOUD': render_cloud_mode()
    elif current_mode == 'SIM': render_matrix_mode()

if __name__ == "__main__":
    main()
