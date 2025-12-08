"""
Tezaver Sim Lab UI Tab
======================

Backtesting and simulation interface.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from tezaver.sim import sim_engine
from tezaver.sim.sim_config import RallySimConfig
from tezaver.sim import sim_presets
from tezaver.sim.sim_scoreboard import (
    run_preset_scoreboard,
    scores_to_dataframe,
    generate_affinity_for_symbol,
)
from tezaver.sim.sim_promotion import load_sim_promotion
from dataclasses import asdict

def render_sim_lab_tab(symbol: str):
    """
    Render Sim Lab tab for experimental backtesting.
    """
    st.markdown("### 🧪 Tezaver Sim Lab v1.1")
    
    # --- Scoreboard Section ---
    st.markdown("### 📊 Preset Performans Panosu")

    @st.cache_data(ttl=600, show_spinner=False)
    def get_cached_affinity_summary(sym: str):
        # Calculates affinity and saves JSON side-effect
        return generate_affinity_for_symbol(symbol=sym)

    if st.button("Bu coin için tüm preset'leri çalıştır", key="btn_run_scoreboard"):
        with st.spinner("Tüm presetler çalıştırılıyor ve analiz ediliyor..."):
            summary = get_cached_affinity_summary(symbol)

        if not summary or not summary.presets:
            st.info("Bu coin için preset sonuçları üretilemedi. (Yetersiz event veya fiyat datası olabilir.)")
        else:
            # 1. Show Badge for Best Strategy
            # 1. Show Badge (Sim v1.5 Promotion > Sim v1.3 Affinity)
            promo_data = load_sim_promotion(symbol)
            promo_badge_shown = False
            
            if promo_data and 'strategies' in promo_data:
                strats = promo_data['strategies']
                # Approved
                approved = [s for s in strats.values() if s.get('status') == 'APPROVED']
                if approved:
                    best_app = max(approved, key=lambda x: x.get('affinity_score', 0))
                    st.success(f"🛡️ **Bulut Önerisi (APPROVED):** {best_app.get('preset_id')} "
                                f"(Skor: {best_app.get('affinity_score'):.0f})")
                    promo_badge_shown = True
                
                # If not approved, check Candidate
                if not promo_badge_shown:
                    candidates = [s for s in strats.values() if s.get('status') == 'CANDIDATE']
                    if candidates:
                        best_cand = max(candidates, key=lambda x: x.get('affinity_score', 0))
                        st.warning(f"🛡️ **Bulut Adayı (CANDIDATE):** {best_cand.get('preset_id')} "
                                   f"(Skor: {best_cand.get('affinity_score'):.0f})")
                        promo_badge_shown = True

            # Fallback to Affinity Badge if no promotion badge shown (or show both?)
            # Let's show Affinity badge as secondary info if not shown, or just always show it if useful.
            # But prompt says "If at least one APPROVED... show a small badge...". 
            # If I show promotion badge, maybe suppress text-heavy affinity badge?
            # Or keep it as "En Uyumlu Strateji" vs "Bulut Önerisi". They might differ (one is just best score, one is safe).
            # I'll keep the affinity badge as it gives detailed "Skor: 83, Not: A" info which is nice.
            
            if summary.best_overall:
                best = summary.best_overall
                # Safe lookup for label
                all_presets = sim_presets.get_all_presets()
                pmap = {p.id: p.label_tr for p in all_presets}
                best_label = pmap.get(best.preset_id, best.preset_id)
                
                # If promo badge shown, make this one info or less prominent?
                # st.success is fine.
                st.info(
                    f"🏆 **En Uyumlu Strateji (Affinity):** {best_label} "
                    f"(Skor: **{best.affinity_score:.0f}**, Not: **{best.affinity_grade}**)"
                )
            
            # 2. Prepare DataFrame from Affinity Results
            # PresetAffinity has metrics + score + grade
            rows = []
            all_presets = sim_presets.get_all_presets()
            pmap = {p.id: p.label_tr for p in all_presets}
            
            for pid, aff in summary.presets.items():
                row = asdict(aff)
                row['preset_label_tr'] = pmap.get(pid, pid) # Enrich label
                rows.append(row)
                
            df_scores = pd.DataFrame(rows)
            
            # Metrik kartları (Recalculate or extract from rows)
            total_presets = len(df_scores)
            best_win = df_scores.loc[df_scores["win_rate"].idxmax()] if not df_scores.empty else None
            best_pnl = df_scores.loc[df_scores["net_pnl_pct"].idxmax()] if not df_scores.empty else None

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Preset Sayısı", total_presets)
            with col2:
                if best_win is not None:
                    st.metric(
                        "En Yüksek Win Rate",
                        f"{best_win['win_rate'] * 100:.1f}%",
                        best_win['preset_label_tr'],
                    )
            with col3:
                if best_pnl is not None:
                     st.metric(
                        "En Yüksek Net PnL",
                        f"{best_pnl['net_pnl_pct'] * 100:.1f}%",
                        best_pnl['preset_label_tr'],
                    )

            st.dataframe(
                df_scores,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "preset_label_tr": st.column_config.TextColumn("Strateji"),
                    "affinity_score": st.column_config.ProgressColumn("Uyum Skoru", min_value=0, max_value=100, format="%.0f"),
                    "affinity_grade": st.column_config.TextColumn("Not"),
                    "timeframe": st.column_config.TextColumn("TF"),
                    "num_trades": st.column_config.NumberColumn("Trade #"),
                    "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1f%%"),
                    "net_pnl_pct": st.column_config.NumberColumn("Net PnL", format="%.1f%%"),
                    "max_drawdown_pct": st.column_config.NumberColumn("Max DD", format="%.1f%%"),
                    "expectancy_pct": st.column_config.NumberColumn("Beklenti/Trd", format="%.2f%%"),
                    "preset_id": None, # Hide internal ID
                    "status": None
                },
            )
            
            # Simple Chart
            if not df_scores.empty and 'affinity_score' in df_scores.columns:
                 # Show Score chart instead of PnL? Or keep PnL? 
                 # PnL is more tangible. Let's keep PnL but maybe sort by it.
                 # Actually let's show PnL.
                 chart_data = df_scores.set_index("preset_label_tr")["net_pnl_pct"]
                 st.bar_chart(chart_data)
                 
    st.divider()

    # --- Session State Init ---
    if "sim_active_preset_id" not in st.session_state:
        st.session_state.sim_active_preset_id = None
    if "sim_customized_from" not in st.session_state:
        st.session_state.sim_customized_from = None
        
    presets = sim_presets.get_all_presets()
    preset_map = {p.id: p for p in presets}
    
    col_settings, col_results = st.columns([1, 2])
    
    with col_settings:
        st.markdown("#### Strateji Ayarları")
        
        # --- 0. Preset Selector ---
        preset_options = ["MANUAL"] + [p.id for p in presets]
        
        def format_preset(pid):
            if pid == "MANUAL":
                return "📝 Manuel (Custom)"
            return preset_map[pid].label_tr

        selected_preset_id = st.selectbox(
            "Strateji Şablonu (Preset)", 
            options=preset_options,
            format_func=format_preset,
            key="sim_preset_selector"
        )
        
        # Handle Preset Selection Change
        if selected_preset_id != "MANUAL":
            # If changed to a specific preset
            p = preset_map[selected_preset_id]
            st.markdown(f"_{p.description_tr}_")
            
            # Apply preset values to session state if just selected or matching
            # We use a button or direct update? Direct update is better.
            # But streamllit re-runs. We need to check if we should update widgets.
            
            # Force update widgets if active preset matches selection
            # OR if we want to apply it now. 
            # Ideally, when selectbox changes, we update the other widgets.
            if st.session_state.sim_active_preset_id != selected_preset_id:
               st.session_state.sim_active_preset_id = selected_preset_id
               st.session_state.sim_customized_from = None
               # Update widget keys
               cfg = p.base_config
               st.session_state.sim_tf = cfg.timeframe
               st.session_state.sim_qual = int(cfg.min_quality_score)
               st.session_state.sim_shapes = cfg.allowed_shapes
               st.session_state.sim_use_trend = (cfg.require_trend_soul_4h_gt is not None)
               if cfg.require_trend_soul_4h_gt: st.session_state.sim_trend_val = int(cfg.require_trend_soul_4h_gt)
               st.session_state.sim_use_rsi = (cfg.require_rsi_1d_gt is not None)
               if cfg.require_rsi_1d_gt: st.session_state.sim_rsi_val = int(cfg.require_rsi_1d_gt)
               st.session_state.sim_tp = float(cfg.tp_pct * 100)
               st.session_state.sim_sl = float(cfg.sl_pct * 100)
               st.session_state.sim_risk = float(cfg.risk_per_trade_pct * 100)
               st.session_state.sim_horizon = int(cfg.max_horizon_bars)
               st.rerun()

        elif selected_preset_id == "MANUAL" and st.session_state.sim_active_preset_id is not None:
             # User explicitly switched to Manual
             st.session_state.sim_active_preset_id = None
             st.session_state.sim_customized_from = None
             st.rerun()
             
        st.divider()

        # 1. Scope
        tf = st.selectbox("Zaman Dilimi", options=["15m", "1h", "4h"], index=1, key="sim_tf")
        
        # 2. Filters
        st.markdown("**Giriş Filtreleri**")
        min_quality = st.slider("Min Kalite Puanı", 0, 100, 50, key="sim_qual")
        
        shapes = st.multiselect(
            "İzin Verilen Şekiller",
            options=["clean", "choppy", "spike", "weak", "unknown"],
            default=["clean", "choppy"],
            key="sim_shapes"
        )
        
        # Context Filters
        use_trend = st.checkbox("4h Trend Soul Filtresi", value=False, key="sim_use_trend")
        trend_thresh = 60
        if use_trend:
            trend_thresh = st.slider("Min 4h Trend Soul", 0, 100, 60, key="sim_trend_val")
            
        use_rsi = st.checkbox("1d RSI Filtresi", value=False, key="sim_use_rsi")
        rsi_thresh = 50
        if use_rsi:
            rsi_thresh = st.slider("Min 1d RSI", 0, 100, 50, key="sim_rsi_val")
            
        # 3. Trade Mgmt
        st.markdown("**İşlem Yönetimi (Spot Long)**")
        tp_pct = st.slider("Hedef Kâr (TP) %", 1.0, 30.0, 5.0, 0.5, key="sim_tp") / 100.0
        sl_pct = st.slider("Stop Loss (SL) %", 0.5, 10.0, 2.0, 0.5, key="sim_sl") / 100.0
        
        risk_pct = st.slider("İşlem Başına Risk % (Sermaye)", 0.1, 5.0, 1.0, 0.1, key="sim_risk") / 100.0
        
        max_bars = st.number_input("Max Bekleme (Bar)", value=48, min_value=5, max_value=200, key="sim_horizon")
        
        start_sim = st.button("🚀 Simülasyonu Başlat", use_container_width=True, type="primary")

        # --- Detect Customization ---
        # If we have an active preset, check if values drifted
        if st.session_state.sim_active_preset_id:
            p = preset_map[st.session_state.sim_active_preset_id]
            c = p.base_config
            
            is_modified = False
            if tf != c.timeframe: is_modified = True
            if min_quality != int(c.min_quality_score): is_modified = True
            if set(shapes) != set(c.allowed_shapes): is_modified = True
            # Check Trend Trigger
            c_trend = c.require_trend_soul_4h_gt
            if use_trend != (c_trend is not None): is_modified = True
            if use_trend and c_trend is not None and float(trend_thresh) != float(c_trend): is_modified = True
            # Check RSI Trigger
            c_rsi = c.require_rsi_1d_gt
            if use_rsi != (c_rsi is not None): is_modified = True
            if use_rsi and c_rsi is not None and float(rsi_thresh) != float(c_rsi): is_modified = True
            
            if abs(tp_pct - c.tp_pct) > 0.0001: is_modified = True
            if abs(sl_pct - c.sl_pct) > 0.0001: is_modified = True
            if abs(risk_pct - c.risk_per_trade_pct) > 0.0001: is_modified = True
            if int(max_bars) != int(c.max_horizon_bars): is_modified = True
            
            if is_modified:
                st.session_state.sim_customized_from = st.session_state.sim_active_preset_id
                st.session_state.sim_active_preset_id = None
                # st.rerun() # Optional, but helps UI update "MANUAL" selection immediately

    with col_results:
        # Header Info
        if st.session_state.sim_active_preset_id:
             p = preset_map[st.session_state.sim_active_preset_id]
             st.info(f"**Aktif Preset:** {p.label_tr}")
        elif st.session_state.sim_customized_from:
             p = preset_map[st.session_state.sim_customized_from]
             st.warning(f"**Modifiye Edildi:** {p.label_tr} üzerinden özelleştirildi.")
        else:
             st.caption("Mod: Tamamen Manuel")

        if start_sim:
            with st.spinner("Geçmiş veriler yükleniyor ve simülasyon çalıştırılıyor..."):
                # 1. Config
                cfg = RallySimConfig(
                    symbol=symbol,
                    timeframe=tf,
                    min_quality_score=float(min_quality),
                    allowed_shapes=shapes,
                    min_future_max_gain_pct=None, # Not filtering by future gain (honest test)
                    require_trend_soul_4h_gt=float(trend_thresh) if use_trend else None,
                    require_rsi_1d_gt=float(rsi_thresh) if use_rsi else None,
                    tp_pct=tp_pct,
                    sl_pct=sl_pct,
                    risk_per_trade_pct=risk_pct,
                    max_horizon_bars=int(max_bars),
                    initial_equity=10000.0
                )
                
                # 2. Data
                events_df = sim_engine.load_rally_events(symbol, tf)
                prices_df = sim_engine.load_price_series(symbol, tf)
                
                if events_df.empty:
                    st.error(f"'{tf}' için rally olayı verisi bulunamadı. Lütfen önce tarama yapın.")
                    return
                if prices_df.empty:
                    st.error(f"'{tf}' için fiyat verisi bulunamadı.")
                    return
                    
                # 3. Filter
                filtered_events = sim_engine.filter_events(events_df, cfg)
                
                if filtered_events.empty:
                    st.warning("Seçilen filtre kriterlerine uyan olay kalmadı.")
                    return
                    
                # 4. Simulate
                trades_df, equity_df = sim_engine.simulate_trades(filtered_events, prices_df, cfg)
                
                # Pass preset info
                results = sim_engine.summarize_results(
                    trades_df, 
                    equity_df,
                    preset_id=st.session_state.sim_active_preset_id,
                    customized_from=st.session_state.sim_customized_from
                )
                
                # 5. Display
                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Toplam Trade", results['num_trades'])
                m2.metric("Win Rate", f"{results['win_rate']*100:.1f}%")
                m3.metric("Toplam PnL", f"{results['total_pnl_pct']*100:.2f}%", help="Başlangıç sermayesine göre % getiri")
                m4.metric("Max Drawdown", f"{results['max_drawdown_pct']*100:.2f}%")
                
                st.markdown("---")
                
                # Equity Curve
                st.markdown("#### Sermaye Eğrisi")
                if not equity_df.empty:
                    st.line_chart(equity_df, x='timestamp', y='equity', color="#00ff00")
                
                # Trade Analysis
                st.markdown("#### İşlem Listesi")
                if not trades_df.empty:
                    # Format for display
                    display_df = trades_df.copy()
                    display_df['PnL %'] = display_df['gross_return_pct'] * 100
                    display_df = display_df[['event_time', 'exit_time', 'exit_reason', 'PnL %', 'rally_shape', 'equity_after']]
                    st.dataframe(display_df.sort_values('event_time', ascending=False), use_container_width=True)
        else:
            if not st.session_state.sim_active_preset_id:
                st.info("👈 Ayarları yapın ve simülasyonu başlatın.")
            
            st.markdown("""
            **Nasıl Çalışır?**
            - **Preset Sistemi**: Hazır strateji şablonlarını kullanarak hızlı başlangıç yapın.
            - **Rally Event**: Sistem taramaları (Time-Labs / 15 Dakika) tarafından tespit edilen sinyalleri kullanır.
            - **Filtreler**: Sadece belirttiğiniz kalitede ve bağlamdaki (Trend, RSI) sinyallere girer.
            - **Spot Long**: Kaldıraçsız, tek yönlü alım simülasyonu.
            """)
