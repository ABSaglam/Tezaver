"""
Daily Radar Tab - UI for Multi-Timeframe Coin Filter
=====================================================
Displays filtered coins in two categories:
- 🚀 Sıçrama (Breakout candidates)
- 📈 Trend (In-trend coins)
"""

import streamlit as st
from tezaver.mining.daily_radar_engine import DailyRadarEngine


def render_daily_radar_tab():
    """Render the Daily Radar UI tab."""
    st.subheader("🧬 GEN-RADAR")
    st.caption("Genetik Karakter (DNA) + Multi-Timeframe Momentum Filtresi.")
    
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        scan_btn = st.button("🔍 Tara", use_container_width=True, type="primary")
    with col2:
        auto_sync = st.checkbox("🔄 Oto-Sync", value=False, help="Taramadan önce verileri Binance'den günceller (Biraz yavaştır)")
        
    if scan_btn:
        with st.spinner("Piyasa verileri güncelleniyor ve koinler taranıyor..." if auto_sync else "Koinler taranıyor..."):
            engine = DailyRadarEngine()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(i, total, symbol):
                progress_bar.progress(i / total)
                status_text.text(f"Taranan: {symbol} ({i}/{total})")
                
            results = engine.scan_all(progress_callback=update_progress, auto_sync=auto_sync)
            
            progress_bar.empty()
            status_text.empty()
            
        # Store results in session
        st.session_state['radar_results'] = results
        
    # Display results
    if 'radar_results' in st.session_state:
        results = st.session_state['radar_results']
        
        if not results:
            st.warning("Filtrelerden geçen coin bulunamadı.")
            return
            
        # Split by category
        breakouts = [r for r in results if r.category == "BREAKOUT"]
        trends = [r for r in results if r.category == "TREND"]
        ninjas = [r for r in results if r.category == "NINJA"]
        watches = [r for r in results if r.category == "WATCH"]
        
        # Summary
        st.success(f"**Toplam {len(results)}** coin filtrelendi → 🚀 Sıçrama: {len(breakouts)} | 📈 Trend: {len(trends)} | 🥷 Ninja: {len(ninjas)} | 👁️ İzle: {len(watches)}")
        
        # Tabs for categories
        tab1, tab2, tab3, tab4 = st.tabs(["🚀 Sıçrama Adayları", "📈 Trend İçindekiler", "🥷 NINJA (Dip Patlaması)", "👁️ İzleme Listesi"])
        
        with tab1:
            if breakouts:
                _render_results_table(breakouts)
            else:
                st.info("Sıçrama adayı yok.")
                
        with tab2:
            if trends:
                _render_results_table(trends)
            else:
                st.info("Trend içinde coin yok.")
                
        with tab3:
            if ninjas:
                st.info("💡 **NINJA Stratejisi:** Bu koinler dipten sert patlama (wick) potansiyeli taşır. **Takip Eden Stop (Trailing Stop)** kullanımı zorunludur. Hedef %20-40 kar alıp çıkmaktır.")
                _render_results_table(ninjas)
            else:
                st.info("Ninja adayı yok.")
                
        with tab4:
            if watches:
                _render_results_table(watches)
            else:
                st.info("İzleme listesi boş.")


def _render_results_table(results):
    """Render a table of radar results."""
    rows = []
    
    # Tier icons
    tier_icons = {
        'S': '🏆', 'A': '⭐', 'B+': '✅', 'B': '🔷', 'B-': '🔹',
        'C+': '⚠️', 'C': '🟠', 'C-': '🔴', 'D': '❌', 'F': '💀'
    }
    
    for r in results:
        icon = tier_icons.get(r.dna_tier, "⚪")
        rows.append({
            "Symbol": r.symbol.replace("USDT", ""),
            "Karakter": f"{icon} {r.dna_tier}",
            "Skor": f"{r.score}/100",
            "ATR%": f"{r.daily.atr_pct:.1f}%",
            "Pozisyon": f"{r.daily.midpoint_pct:.0f}%",
            "RSI": f"{r.momentum.rsi:.0f}",
            "Yeşil Gün": r.daily.green_days,
            "Squeeze": "✅" if r.daily.bb_squeeze else "",
            "Direnç": "⚠️" if r.daily.near_resistance else "",
        })
    
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Symbol": st.column_config.TextColumn("Coin", width="small"),
            "Karakter": st.column_config.TextColumn("DNA Tier", width="small"),
            "Skor": st.column_config.TextColumn("Skor", width="small"),
            "ATR%": st.column_config.TextColumn("ATR%", width="small"),
            "Pozisyon": st.column_config.TextColumn("5D Poz.", width="small"),
            "RSI": st.column_config.TextColumn("RSI 4H", width="small"),
            "Yeşil Gün": st.column_config.NumberColumn("Yeşil", width="small"),
            "Squeeze": st.column_config.TextColumn("Sqz", width="small"),
            "Direnç": st.column_config.TextColumn("Dir.", width="small"),
        }
    )
