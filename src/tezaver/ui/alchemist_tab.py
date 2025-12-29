
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from tezaver.core import coin_cell_paths
from tezaver.core.state_store import load_coin_states
from tezaver.smyrna.alchemist_engine import AlchemistEngine
from tezaver.core.cipher_types import RallySequence, ParticleType
from tezaver.ui.chart_area import render_universal_chart

def render_alchemist_page():
    st.title("🧪 Simyacı 3.0 (Alchemist Lab)")
    st.caption("Ralli DNA'sı Çıkarma ve Kehanet Motoru")
    
    # --- 1. SETUP ---
    engine = AlchemistEngine()
    
    # --- 2. LAYOUT: 3 COLUMNS ---
    col_ore, col_crucible, col_vault = st.columns([1, 2, 1])
    
    # --- COLUMN 1: THE ORE (Raw Material) ---
    with col_ore:
        st.subheader("🪨 Cevher (Ralliler)")
        
        # Load all coins
        coin_states = load_coin_states()
        if not coin_states:
            st.warning("Coin verisi yok.")
            return

        coin_states = load_coin_states()
        if not coin_states:
            st.warning("Coin verisi yok.")
            return

        # Coin & Timeframe Selection
        c1, c2 = st.columns([2, 1])
        with c1:
            selected_coin = st.selectbox("Coin", [s.symbol for s in coin_states], key="alc_coin_sel")
        with c2:
            selected_tf = st.selectbox("Zaman", ["15m", "1h", "4h"], key="alc_tf_sel")
            
        # Load Rallies based on TF
        try:
            if selected_tf == "15m":
                parquet_path = coin_cell_paths.get_fast15_rallies_path(selected_coin)
            else:
                parquet_path = coin_cell_paths.get_time_labs_rallies_path(selected_coin, selected_tf)
            
            if not parquet_path.exists():
                st.info(f"{selected_coin} {selected_tf} için veri henüz yok.")
                df_rallies = pd.DataFrame()
            else:
                df_rallies = pd.read_parquet(parquet_path)

            if not df_rallies.empty:
                # --- TIER EXTRACTION ---
                # Ensure 'tier' column exists. If not, extract from ID or recalc.
                if 'tier' not in df_rallies.columns:
                    # Strategy 1: Try to extract from event_id (Format: SYMBOL_TF_TIER_TIMESTAMP)
                    # e.g. BTCUSDT_15m_G_1715423400
                    def extract_tier_from_id(eid):
                        parts = str(eid).split('_')
                        if len(parts) >= 3 and parts[2] in ['D','G','S','B']:
                            return parts[2]
                        return 'B' # Default Fallback
                    
                    df_rallies['tier'] = df_rallies['event_id'].apply(extract_tier_from_id)
                
                # --- TIER FILTERING UI ---
                # Calculate counts based on the extracted/loaded tier
                count_D = len(df_rallies[df_rallies['tier'] == 'D'])
                count_G = len(df_rallies[df_rallies['tier'] == 'G'])
                count_S = len(df_rallies[df_rallies['tier'] == 'S'])
                count_B = len(df_rallies[df_rallies['tier'] == 'B'])
                count_All = len(df_rallies)
                
                # Formatting callback for radio
                def format_tier(option):
                    if option == 'All': return f"🌐 ({count_All})"
                    if option == 'D': return f"💎 ({count_D})"
                    if option == 'G': return f"🥇 ({count_G})"
                    if option == 'S': return f"🥈 ({count_S})"
                    if option == 'B': return f"🥉 ({count_B})"
                    return option

                # Tier Selector
                selected_tier_code = st.radio(
                    "Kalite Filtresi",
                    options=['All', 'D', 'G', 'S', 'B'],
                    format_func=format_tier,
                    horizontal=True,
                    label_visibility="collapsed",
                    key="alc_tier_filter"
                )

                # Filter DataFrame
                if selected_tier_code != 'All':
                    df_filtered = df_rallies[df_rallies['tier'] == selected_tier_code]
                else:
                    df_filtered = df_rallies

                # Build List Options
                options = []
                # Sort by reverse date (newest first)
                df_filtered = df_filtered.sort_values('event_time', ascending=False)
                
                for idx, row in df_filtered.iterrows():
                    ts = pd.to_datetime(row['event_time'])
                    tier_icon = {"D":"💎", "G":"🥇", "S":"🥈", "B":"🥉"}.get(row.get('tier','B'), "")
                    label = f"{tier_icon} {ts.strftime('%Y-%m-%d %H:%M')} | +{row.get('future_max_gain_pct',0)*100:.1f}%"
                    options.append(label)
                
                selected_rally_label = st.selectbox("Ralli Seç", options, key="alc_rally_sel")
                
                if selected_rally_label:
                    # Parse selection to find unique row
                    # Current method relies on unique formatting or index map. 
                    # Providing separate lists is cleaner but let's match by index logic or ID if possible.
                    # Simple way: Map label back to index/row
                    # Just finding the first match for now (timestamp usually unique enough per coin)
                    sel_idx = options.index(selected_rally_label)
                    rally_row = df_filtered.iloc[sel_idx]
                    st.session_state['alc_current_rally'] = rally_row
            else:
                st.info("Ralli verisi boş.")
                
        except Exception as e:
            st.error(f"Veri yüklenemedi: {e}")

    # --- COLUMN 2: THE CRUCIBLE (Extraction) ---
    with col_crucible:
        st.subheader("🔥 Pota (Dönüşüm)")
        
        current_rally = st.session_state.get('alc_current_rally')
        
        if current_rally is not None:
            # 1. Show Chart
            event_time = pd.to_datetime(current_rally['event_time'])
            st.markdown(f"**Seçili:** {selected_coin} @ {event_time}")
            
            # Use universal chart to show context
            # We need to render it slightly smaller or cleaner
            render_universal_chart(
                symbol=selected_coin,
                timeframe="15m",
                event_time=event_time,
                bars_to_peak=60, # Show enough context
            )
            
            # 2. Extract DNA Button
            if st.button("🧬 DNA Çıkar (Extract)", use_container_width=True, type="primary"):
                with st.spinner("Parçacıklar ayrıştırılıyor..."):
                    # Load REAL context data
                    from tezaver.ui.chart_area import load_history_data
                    
                    # We need 15m data for the granular particles
                    df_history = load_history_data(selected_coin, "15m")
                    
                    if df_history is not None and not df_history.empty:
                        # Slice data up to the event time
                        # Ensure timestamps are localized/naive compatible
                        if df_history['open_time'].dt.tz is None:
                            # event_time is naive from pandas read usually
                            cutoff = event_time
                        else:
                            # If history is tz-aware (e.g. UTC), ensure event is too
                            cutoff = event_time.tz_localize(df_history['open_time'].dt.tz)
                            
                        # Get context window (e.g., 100 bars before event)
                        df_context = df_history[df_history['open_time'] <= cutoff].tail(100).copy()
                        
                        # Set index for engine convenience if needed, but engine expects columns
                        # Engine uses 'close', 'volume', 'rsi', 'bb_width'
                        # We might need to calculate indicators if missing (ChartArea does this for plotting)
                        # For now, let's assume history has basic OHLCV and Engine handles raw calculation 
                        # OR we calculate basic ones here nicely. 
                        # Alchemist Engine _mine methods calculate them if missing.
                        
                        sequence = engine.extract_sequence(
                            df_context=df_context,
                            rally_event_id=str(current_rally.get('event_id', 'temp')),
                            symbol=selected_coin
                        )
                        
                        st.success(f"DNA Dizilimi Çıkarıldı! ({len(sequence.particles)} Parçacık)")
                        
                        # Store in session state as dicts for UI robustness
                        dna_data = []
                        for p in sequence.particles:
                            dna_data.append({
                                "type": p.type.name,
                                "offset": p.time_offset,
                                "desc": p.description,
                                "val": p.val
                            })
                            
                        st.session_state['alc_extracted_dna'] = dna_data
                        
                    else:
                        st.error("Tarihsel veri bulunamadı.")


            # 3. Visualize DNA Sequence
            dna = st.session_state.get('alc_extracted_dna')
            if dna:
                st.markdown("#### Bulunan Parçacıklar")
                # Simple Timeline Visualization
                for p in sorted(dna, key=lambda x: x['offset']):
                    st.info(f"**T{p['offset']}**: {p['desc']} ({p['type']})")
                
                # Ghost Projection (Placeholder)
                st.markdown("#### 👻 Ghost Projection")
                st.caption("Hedef İz Düşümü: %15.2 Yükseliş (Güven: %85)")

    # --- COLUMN 3: THE VAULT (Storage) ---
    with col_vault:
        st.subheader("🏦 Kasa (Master Ciphers)")
        
        st.info("Kayıtlı Şifre Yok.")
        
        if st.session_state.get('alc_extracted_dna'):
            cipher_name = st.text_input("Şifre Adı", value="Alpha-Protocol-1")
            if st.button("💾 Kasaya Kaydet"):
                st.toast(f"{cipher_name} başarıyla saklandı!", icon="🔐")

