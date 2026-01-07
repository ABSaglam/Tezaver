import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tezaver.core import config, coin_cell_paths
from tezaver.supernova.supernova_detector import SuperNovaDetector

def render_supernova_page():
    st.title("💥 SuperNova Stüdyosu")
    st.markdown("---")
    
    # 1. State Initialization
    if 'sn_detector' not in st.session_state:
        st.session_state.sn_detector = SuperNovaDetector()
    if 'sn_results' not in st.session_state:
        st.session_state.sn_results = None
    
    # 2. Controls
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        scan_days = st.selectbox("Tarama Süresi", [30, 90, 180, 365], index=0, format_func=lambda x: f"{x} Gün")
    with col2:
        min_vol = st.number_input("Min Hacim (7x+)", value=7.0, step=0.5)
    with col3:
    # Tabs
    tab1, tab2 = st.tabs(["🕵️ Klasik Dedektör", "🚀 Super Momentum (Scraper)"])
    
    with tab1:
        render_classic_detector(scan_days, min_vol)
        
    with tab2:
        render_super_momentum_tab()

def render_super_momentum_tab():
    st.subheader("🚀 Super Momentum Scraper")
    st.markdown("Reaktif Scalp Stratejisi: **5x Hacim** + **RSI > 70** + **Büyük Mum (%2+)**")
    st.info("💡 **Olasılık:** %86 Başarı (Win Rate) | **Ortalama Kazanç:** %19.45")
    
    if st.button("Taramayı Başlat (Super Momentum)", key="btn_sm_scan"):
        from tezaver.mining.super_momentum_miner import SuperMomentumMiner
        miner = SuperMomentumMiner()
        
        with st.spinner("Piyasa taranıyor..."):
            results = miner.mine(lookback_bars=200)
            
        if not results:
            st.warning("Şu an aktif bir Super Momentum sinyali bulunamadı.")
            return
            
        st.success(f"{len(results)} Sinyal Bulundu!")
        
        # Display
        data = []
        for r in results:
            data.append({
                "Tarih": r.event_time,
                "Sembol": r.symbol,
                "Fiyat": r.price,
                "RSI": r.rsi,
                "Hacim (x)": r.vol_factor,
                "Mum Boyu (%)": r.candle_size_pct,
                "Tier": r.tier
            })
            
        df = pd.DataFrame(data).sort_values("Tarih", ascending=False)
        
        st.dataframe(
            df,
            column_config={
                "Tarih": st.column_config.DatetimeColumn(format="DD.MM HH:mm"),
                "Fiyat": st.column_config.NumberColumn(format="%.4f"),
                "RSI": st.column_config.NumberColumn(format="%.1f"),
                "Hacim (x)": st.column_config.NumberColumn(format="%.1fx"),
                "Mum Boyu (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
            hide_index=True,
            use_container_width=True
        )

def render_classic_detector(scan_days, min_vol):
    st.info("🧬 **DNA v3:** 15m Momentum + MTF (1s/4s/1g) MACD Onayı ile en saf sinyalleri yakalar.")

    if st.button("🚀 Global Taramayı Başlat (100 Koin)", use_container_width=True):
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        coins = config.DEFAULT_COINS
        num_coins = len(coins)
        
        for i, symbol in enumerate(coins):
            # status_text.text(f"Taranıyor: {symbol} ({i+1}/{num_coins})")
            progress_bar.progress((i + 1) / num_coins)
            
            try:
                # Load 15m Data
                p15 = coin_cell_paths.get_history_file(symbol, "15m")
                if not p15.exists(): continue
                df15 = pd.read_parquet(p15)
                
                # Run Detection
                detector = st.session_state.sn_detector
                df15 = detector.calculate_indicators(df15)
                
                # Load MTF Context
                p1h = coin_cell_paths.get_history_file(symbol, "1h")
                p4h = coin_cell_paths.get_history_file(symbol, "4h")
                p1d = coin_cell_paths.get_history_file(symbol, "1d")
                
                df1h = pd.read_parquet(p1h) if p1h.exists() else None
                df4h = pd.read_parquet(p4h) if p4h.exists() else None
                df1d = pd.read_parquet(p1d) if p1d.exists() else None
                
                if df1h is not None: df1h = detector.calculate_indicators(df1h)
                if df4h is not None: df4h = detector.calculate_indicators(df4h)
                
                # Filter by timeframe
                cutoff = df15['datetime'].max() - timedelta(days=scan_days)
                df15_scan = df15[df15['datetime'] >= cutoff]
                
                if df15_scan.empty: continue
                
                res = detector.analyze_backtest(df15, symbol=symbol, df_1h=df1h, df_4h=df4h, df_1d=df1d)
                
                # Only keep results within the selected scan duration
                res = [r for r in res if r['datetime'] >= cutoff]
                all_results.extend(res)
                
            except Exception as e:
                # st.warning(f"Error processing {symbol}: {e}")
                continue
        
        st.session_state.sn_results = all_results
        status_text.text("Tarama Tamamlandı! ✅")
        progress_bar.empty()

    # 3. Display Results
    if st.session_state.sn_results:
        df_res = pd.DataFrame(st.session_state.sn_results)
        
        if df_res.empty:
            st.warning("Belirtilen kriterlerde sinyal bulunamadı.")
            return

        # Tier Formatting
        def format_tier(t):
            icons = {
                "DIAMOND": "💎 Diamond",
                "GOLD": "🥇 Gold",
                "SILVER": "🥈 Silver",
                "BRONZE": "🥉 Bronze",
                "IRON": "🧱 Iron"
            }
            return icons.get(t, t)
            
        df_res['Sıralama'] = df_res['tier'].apply(format_tier)
        
        # Sort by Datetime (Latest First)
        df_res = df_res.sort_values('datetime', ascending=False)
        
        # Display Summary
        c1, c2, c3, c4 = st.columns(4)
        total = len(df_res)
        winners = len(df_res[df_res['tier'].isin(['DIAMOND', 'GOLD', 'SILVER'])])
        dnas = len(df_res[df_res['dna_v2'] == "✅"])
        killers = len(df_res[df_res['killer_blow'] == "🔥"])
        
        c1.metric("Toplam Sinyal", total)
        c2.metric("Toplam Kazanan", winners, delta=f"%{winners/total*100:1.1f}" if total > 0 else "0")
        c3.metric("DNA Onaylı", dnas)
        c4.metric("Killer Blow", killers)

        # Filters on UI
        st.markdown("### 🔍 Sinyal Filtreleri")
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            only_dna = st.checkbox("Sadece DNA Onaylıları Göster (✅)", value=False)
        with f_col2:
            only_killer = st.checkbox("Sadece Killer Blow Göster (🔥)", value=False)
            
        view_df = df_res.copy()
        if only_dna: view_df = view_df[view_df['dna_v2'] == "✅"]
        if only_killer: view_df = view_df[view_df['killer_blow'] == "🔥"]

        st.dataframe(
            view_df[['datetime', 'symbol', 'vol_ratio', 'macd_color', 'dna_v2', 'killer_blow', 'Sıralama', 'max_gain', 'max_loss']],
            column_config={
                "datetime": "Tarih",
                "symbol": "Koin",
                "vol_ratio": st.column_config.NumberColumn("Hacim (x)", format="%.1f"),
                "macd_color": "MACD",
                "dna_v2": "DNA v2",
                "killer_blow": "K.Blow",
                "max_gain": st.column_config.NumberColumn("Max Kazanç (%)", format="%.1f%%"),
                "max_loss": st.column_config.NumberColumn("Zarar/Risk (%)", format="%.1f%%"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Taramayı başlatmak için yukarıdaki butona tıklayın.")

if __name__ == "__main__":
    render_supernova_page()
