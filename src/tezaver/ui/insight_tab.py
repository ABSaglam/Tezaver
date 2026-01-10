import streamlit as st
import pandas as pd
from datetime import datetime
import random
from tezaver.core import system_state
from tezaver.core import state_store
from tezaver.core.rally_store import RallyStore
from tezaver.mining.daily_radar_engine import DailyRadarEngine

def render_insight_tab():
    # --- 1. WELCOME & DATE ---
    now = datetime.now()
    date_str = now.strftime("%d %B %Y, %A") # Requires locale setting or manual map for Turkish days if system locale is en
    
    # Simple Turkish Month/Day map if locale is not guaranteed
    tr_days = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    tr_months = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}
    
    day_name = tr_days.get(now.strftime("%A"), now.strftime("%A"))
    month_name = tr_months.get(now.strftime("%B"), now.strftime("%B"))
    formatted_date = f"{now.day} {month_name} {now.year}, {day_name}"
    
    # --- DATA LOADING ---
    store = RallyStore()
    all_rallies = store.list_rallies(limit=5000)
    
    now_ts = pd.Timestamp.now()
    rallies_24h = [r for r in all_rallies if (now_ts - pd.Timestamp(r['event_time'])).total_seconds() < 86400]
    
    pending_approval = [r for r in all_rallies if (r.get('rev_data') or {}).get('status') not in ['APPROVED', 'REJECTED']]
    unlabeled = [r for r in all_rallies if (r.get('rev_data') or {}).get('status') == 'APPROVED' and not (r.get('molder_data') or {}).get('archetype')]

    sys_s = system_state.load_state()

    # Determine greeting based on hour
    hour = now.hour
    if 6 <= hour < 11:
        greeting = "Günaydın"
    elif 11 <= hour < 18:
        greeting = "İyi Günler"
    elif 18 <= hour < 23:
        greeting = "İyi Akşamlar"
    else:
        greeting = "İyi Geceler"

    st.title(f"👋 {greeting} Ali, Sistem Hazır.")
    
    # --- 2. SURPRISE (Daily Wisdom) - SWAPPED POSITION ---
    quotes = [
        "\"Piyasa her zaman haklıdır, ama her zaman mantıklı değildir.\"",
        "\"Fırsatlar gelir ve geçer, disiplin kalıcıdır.\"",
        "\"En iyi işlem, yapmadığın işlemdir (bazen).\"",
        "\"Trend senin dostundur, dönüşü görene kadar.\"",
        "\"Rastgelelik içinde düzen arıyoruz; Simyacı bunu bulacak.\"",
        "\"Sabır, en keskin kılıçtır.\"",
        "\"Veri gürültüdür, bağlam bilgidir, kalıp ise bilgeliktir.\"",
        "\"Küçük kayıplar işin maliyetidir, büyük kayıplar ise hatadır.\""
    ]
    daily_quote = random.choice(quotes)
    st.markdown(f"✨ *{daily_quote}*")

    # Explicit styling for DATE (Below quote)
    st.markdown(f"<div style='font-size: 1.1rem; color: #888; font-weight: 400; margin-top: 10px; margin-bottom: 20px;'>📅 {formatted_date}</div>", unsafe_allow_html=True)

    st.markdown("---")
    
    # --- 2.5 SMART AGENDA (Tezaver Ajanda) ---
    st.subheader("📝 Bugün Yapacaklarım")
    
    from tezaver.core import agenda_manager
    import tezaver.core.agenda_manager as am
    
    # Grid for Agenda
    c_agenda_sys, c_agenda_user = st.columns([1, 1])
    
    from tezaver.core.priority_manager import sort_rallies_by_priority

    # --- A. SYSTEM TASKS (Auto) ---
    with c_agenda_sys:
        st.markdown("**🤖 Sistem Görevleri**")
        st.caption("Otomatik görev akışı devre dışı bırakıldı.")
        
        # Always check system health
        if sys_s.last_full_pipeline_status != "success":
             if st.button("⚠️ Sistem Sağlığını Kontrol Et", key="sys_health_chk", use_container_width=True):
                 st.session_state['nav_selection'] = "⚙️ Sistem Paneli"
                 st.rerun()

    # --- B. PERSONAL NOTES (User) ---
    with c_agenda_user:
        st.markdown("**🧠 Kişisel Notlar**")
        
        # Input
        new_task = st.text_input("Not ekle...", key="agenda_new_input", placeholder="Örn: ETH 15m takip et", label_visibility="collapsed")
        if new_task:
            am.add_coltask(new_task)
            # Hack to clear input? st.rerun is easiest
            # But text_input retains value unless cleared via logic.
            # We can rely on rerun clearing it if key is changing or we manage it.
            # Simple rerun works usually if key is tied to state.
            st.rerun()
            
        # List
        agenda_data = am.load_agenda()
        user_tasks = agenda_data.get('tasks', [])
        
        if not user_tasks:
            st.caption("Henüz not yok.")
        else:
            for i, task in enumerate(user_tasks):
                # Layout: Checkbox | Text | Del
                c_chk, c_txt, c_del = st.columns([1, 8, 1])
                with c_chk:
                    is_done = st.checkbox("", value=task['done'], key=f"task_chk_{i}")
                    if is_done != task['done']:
                        am.toggle_task(i, is_done)
                        st.rerun()
                with c_txt:
                    style = "text-decoration: line-through; color: gray;" if task['done'] else ""
                    st.markdown(f"<div style='padding-top: 5px; {style}'>{task['text']}</div>", unsafe_allow_html=True)
                with c_del:
                    if st.button("x", key=f"del_task_{i}", type="tertiary"):
                        am.delete_task(i)
                        st.rerun()

    st.markdown("---")

    # --- 4. AMBUSH RADAR (The Pusu Pulse) ---
    st.subheader("🎯 Pusu Radarı (Ambush)")
    st.caption("Fırlamaya en hazır, sıkışmış yüksek kaliteli koinler.")
    
    # Initialize Engine
    radar_engine = DailyRadarEngine()
    
    # Grid for Refresh & Last Update
    c_rad_btn, c_rad_info = st.columns([1, 4])
    
    with c_rad_btn:
        if st.button("📡 Radar Yenile", use_container_width=True, help="Binance'den taze verileri çekip taramayı başlatır."):
            with st.spinner("Veriler çekiliyor ve taranıyor..."):
                radar_results = radar_engine.scan_all(refresh_data=True)
                st.session_state['last_radar_results'] = radar_results
                st.session_state['last_radar_time'] = datetime.now().strftime("%H:%M")
                st.rerun()
                
    with c_rad_info:
        last_t = st.session_state.get('last_radar_time', "-")
        st.markdown(f"<div style='padding-top: 10px; color: gray;'>Son Tarama: {last_t}</div>", unsafe_allow_html=True)

    # Display Results
    radar_results = st.session_state.get('last_radar_results', [])
    if not radar_results:
        # Initial scan if session is empty (without refresh_data to be fast)
        with st.spinner("Mevcut veriler taranıyor..."):
            radar_results = radar_engine.scan_all(refresh_data=False)
            st.session_state['last_radar_results'] = radar_results
            st.session_state['last_radar_time'] = datetime.now().strftime("%H:%M")
    
    if radar_results:
        # Filter for AMBUSH, TREND, NINJA
        ambush_list = [r for r in radar_results if r.category == 'AMBUSH']
        trend_list = [r for r in radar_results if r.category == 'TREND']
        
        c_ambush, c_trend = st.columns(2)
        
        with c_ambush:
            st.markdown("**🏹 Pusu Adayları (Breakout Readiness)**")
            if ambush_list:
                df_ambush = pd.DataFrame([{
                    "Koin": r.symbol.replace("USDT", ""),
                    "Tier": r.dna_tier,
                    "Puan": r.score,
                    "Mid%": f"{r.daily.midpoint_pct:.1f}%",
                    "RSI": f"{r.momentum.rsi:.1f}"
                } for r in ambush_list])
                st.dataframe(df_ambush, hide_index=True, use_container_width=True)
            else:
                st.caption("Şu an kriterlere uyan pusu adayı yok.")
                
        with c_trend:
            st.markdown("**📈 Trend Gücü (Ongoing Rallies)**")
            if trend_list:
                df_trend = pd.DataFrame([{
                    "Koin": r.symbol.replace("USDT", ""),
                    "Tier": r.dna_tier,
                    "Puan": r.score,
                    "ATR%": f"{r.daily.atr_pct:.1f}%"
                } for r in trend_list])
                st.dataframe(df_trend, hide_index=True, use_container_width=True)
            else:
                st.caption("Sistemde aktif trend sinyali yok.")
    else:
        st.info("Henüz radar sinyali bulunamadı. Lütfen radarı yenileyin.")

    st.markdown("---")

    # --- 4. ACTION CARDS (Workflow) ---
    st.subheader("🚀 Komuta Paneli")
    
    c_act1, c_act2, c_act3 = st.columns(3)
    
    with c_act1:
        st.info(f"**Revizyon:** {len(pending_approval)} Aday")
        if st.button("🎯 İncelemeye Başla", use_container_width=True):
            st.session_state['nav_selection'] = "🎯 Revize"
            st.rerun()
            
    with c_act2:
        st.warning(f"**Kalıpçı:** {len(unlabeled)} Etiketlenecek")
        if st.button("🏭 Fabrikaya Git", use_container_width=True):
            st.session_state['nav_selection'] = "📐 Kalıpçı"
            # Optional: Force gallery mode if I could access sub-state, but default is fine
            st.rerun()
            
    with c_act3:
        st.success("**Simyacı:** Lab Hazır")
        if st.button("🧪 Analize Git", use_container_width=True):
            st.session_state['nav_selection'] = "🧪 Simyacı"
            st.rerun()

    st.markdown("---")

    # --- 5. MARKET RADAR (Bottom Glimpse) ---
    st.markdown("### 🔥 Piyasa Radarı (HOT)")
    # Re-use load_market_overview logic quickly or just list hot coins
    from tezaver.insight.insight_engine import load_market_overview
    try:
        df = load_market_overview()
        if not df.empty:
            hot_df = df[df['Radar'].str.contains('HOT', na=False)]
            if not hot_df.empty:
                st.dataframe(
                    hot_df[['Symbol', 'Score', 'Lane', 'Radar']], 
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.caption("Şu an 'HOT' statüsünde coin yok. Piyasa sakin.")
        else:
            st.caption("Radar verisi yüklenemedi.")
    except:
        st.caption("Radar bağlantısı kurulamadı.")
