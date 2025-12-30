
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
    
    # =========================================================================
    # SECTION 1: THE ORE (Horizontal Top Bar)
    # =========================================================================
    
    with st.container():
        st.subheader("🪨 Cevher (Ralliler)")
        
        coin_states = load_coin_states()
        if not coin_states:
            st.warning("Coin verisi yok.")
            return

        # Top Bar Controls: 3 Columns like Molder
        c_coin, c_time, c_tier = st.columns([1, 1, 3])
        
        with c_coin:
            selected_coin = st.selectbox("Coin", [s.symbol for s in coin_states], key="alc_coin_sel")
        
        with c_time:
            selected_tf = st.selectbox("Zaman", ["15m", "1h", "4h"], key="alc_tf_sel")
            
        # Data Loading (Via RallyAssembler)
        from tezaver.foundry.rally_assembler import RallyAssembler
        assembler = RallyAssembler()
        
        try:
             # Get Approved & Ready Rallies
             alchemist_rallies = assembler.get_alchemist_ready_rallies(selected_coin, selected_tf)
             
             if not alchemist_rallies:
                 st.info(f"{selected_coin} {selected_tf} için Simyacı'ya uygun (Approved) ralli yok.")
                 
        except Exception as e:
            st.error(f"Veri yükleme hatası: {e}")
            alchemist_rallies = []

        # Tier Logic & Grouping (Standardized Molder Style)
        from tezaver.ui.ony_tab import TIERS
        from tezaver.core.molds import Archetype, ARCHETYPE_LABELS
        
        tier_groups = {t: [] for t in TIERS}
        tier_groups["OTHER"] = []
        
        # Sort by Time (Newest First)
        alchemist_rallies.sort(key=lambda x: x.event_time, reverse=True)
        
        for r in alchemist_rallies:
            t = r.tier
            if t not in tier_groups: t = "OTHER"
            tier_groups[t].append(r)
            
        # TIER SELECTOR
        tier_options = []
        for t in TIERS:
            count = len(tier_groups[t])
            tier_options.append(f"{t} ({count})")
            
        with c_tier:
            # Default to session or Diamond
            if 'alc_selected_tier' not in st.session_state:
                st.session_state['alc_selected_tier'] = "DIAMOND"
            
            def get_clean_tier(opt): return opt.split(" (")[0]
            
            current_sel_idx = 0
            if st.session_state['alc_selected_tier'] in TIERS:
                current_sel_idx = TIERS.index(st.session_state['alc_selected_tier'])
                
            selected_tier_label = st.radio(
                "Tier", 
                tier_options, 
                horizontal=True, 
                key="alc_tier_radio",
                label_visibility="collapsed",
                index=current_sel_idx
            )
            selected_tier = get_clean_tier(selected_tier_label)
            st.session_state['alc_selected_tier'] = selected_tier
            
        # LIST SELECTOR (Full Width)
        current_list_items = tier_groups.get(selected_tier, [])
        options = []
        list_map = {}
        
        if not current_list_items:
            st.info(f"🔍 {selected_tier} katmanında uygun ralli yok.")
            st.session_state['alc_current_rally'] = None
        else:
            # Helper for Icons (Local or Imported)
            def get_arch_icon_local(arch_code):
                if not arch_code: return "❓"
                try:
                    # If arch_code is enum value string
                    if isinstance(arch_code, str):
                        # Try to find enum member
                        try:
                            a_enum = Archetype(arch_code)
                            lbl = ARCHETYPE_LABELS.get(a_enum, "")
                            return lbl.split(" ")[-1] if " " in lbl else "🏷️"
                        except: return "🏷️"
                    return "🏷️"
                except:
                    return "🏷️"

            for r in current_list_items:
                ts_str = r.event_time.strftime('%Y-%m-%d %H:%M')
                
                arch_icon = get_arch_icon_local(r.archetype)
                
                # Format: [TIER] [REV] [ARCH] DATE | GAIN | BARS
                rev_icon = "🛠️" if r.is_revised else ""
                tier_icon = r.get_icon()
                if tier_icon == "🏷️": tier_icon = {"DIAMOND":"💎","GOLD":"🥇","SILVER":"🥈","BRONZE":"🥉"}.get(r.tier, "🔹")
                
                arch_display = f" {arch_icon}" if (r.archetype and r.archetype != "None") else ""
                
                label = f"{tier_icon} {rev_icon}{arch_display} {ts_str} | +{r.gain_pct*100:.1f}% | {max(1, r.bars_to_peak)}bar"
                
                options.append(label)
                list_map[label] = r
            
            # Full Width Selectbox
            default_idx = 0
            selected_rally_label = st.selectbox("Ralli Seçiniz", options, index=default_idx, key="alc_rally_sel", label_visibility="collapsed")
            
            if selected_rally_label:
                st.session_state['alc_current_rally'] = list_map[selected_rally_label]

    st.markdown("---")

    # =========================================================================
    # SECTION 2: THE LABORATORY (Crucible + Vault)
    # =========================================================================
    
    col_crucible, col_vault = st.columns([3, 1])
    
    # --- COLUMN 2 (Left): THE CRUCIBLE (Extraction) ---
    with col_crucible:
        st.subheader("🔥 Pota (Dönüşüm)")
        
        current_rally = st.session_state.get('alc_current_rally')
        
        if current_rally is not None:
            # 1. Show Chart
            event_time = pd.to_datetime(current_rally.event_time)
            st.markdown(f"**Seçili:** {selected_coin} @ {event_time}")
            
            # Chart (Use Sniper Studio version to show Entry/Exit revisions)
            from tezaver.ui.chart_area import render_sniper_studio_chart
            
            try:
                render_sniper_studio_chart(
                    symbol=selected_coin,
                    timeframe="15m",
                    event_time=event_time,
                    bars_to_peak=current_rally.bars_to_peak or 60,
                    entry_offset=current_rally.entry_offset or 0,
                    exit_offset=current_rally.exit_offset or (current_rally.bars_to_peak or 60)
                )
            except Exception as e:
                st.error(f"Grafik hatası: {e}")
            
            # 2. Extract DNA Button
            if st.button("🧬 DNA Çıkar (Extract)", use_container_width=True, type="primary"):
                with st.spinner("Parçacıklar ayrıştırılıyor..."):
                    from tezaver.ui.chart_area import load_history_data
                    
                    df_history = load_history_data(selected_coin, "15m")
                    
                    if df_history is not None and not df_history.empty:
                        if df_history['open_time'].dt.tz is None:
                            cutoff = event_time
                        else:
                            cutoff = event_time.tz_localize(df_history['open_time'].dt.tz)
                            
                        df_context = df_history[df_history['open_time'] <= cutoff].tail(100).copy()
                        
                        sequence = engine.extract_sequence(
                            df_context=df_context,
                            rally_event_id=str(current_rally.event_id),
                            symbol=selected_coin
                        )
                        
                        st.success(f"DNA Dizilimi Çıkarıldı! ({len(sequence.particles)} Parçacık)")
                        
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
                for p in sorted(dna, key=lambda x: x['offset']):
                    st.info(f"**T{p['offset']}**: {p['desc']} ({p['type']})")
                
                st.markdown("#### 👻 Ghost Projection")
                st.caption("Hedef İz Düşümü: %15.2 Yükseliş (Güven: %85)")
    
    # --- COLUMN 3 (Right): THE VAULT (Storage) ---
    # --- COLUMN 3 (Right): THE VAULT (Storage) ---
    with col_vault:
        st.subheader("🏦 Kasa (Master Ciphers)")
        
        # Load Ciphers
        saved_ciphers = engine.load_master_ciphers()
        
        if not saved_ciphers:
            st.info("Kayıtlı Şifre Yok.")
        else:
            st.success(f"📚 {len(saved_ciphers)} Şifre Mevcut")
            for mc in saved_ciphers:
                with st.expander(f"🔐 {mc.name} ({mc.conquest_score:.1f})"):
                    st.caption(f"Signature: {mc.sequence_signature[:20]}...")
                    st.caption(f"Win Rate: %{mc.win_rate*100:.0f} | Gain: %{mc.avg_gain_pct:.1f}")
        
        st.divider()
        
        # Save Interaction
        dna_data = st.session_state.get('alc_extracted_dna')
        current_rally_obj = st.session_state.get('alc_current_rally')
        
        if dna_data and current_rally_obj is not None:
            st.markdown("#### 💾 Şifre Kaydet")
            cipher_name = st.text_input("Şifre Adı", value=f"Protocol-{datetime.now().strftime('%H%M')}")
            
            if st.button("💾 Kasaya Kaydet", type="primary"):
                # 1. Reconstruct RallySequence
                # We need to rebuild particles from dict
                particles = []
                for p_dict in dna_data:
                    # Map string type back to Enum
                    ptype_str = p_dict['type']
                    if "." in ptype_str: ptype_str = ptype_str.split(".")[-1]
                    
                    try:
                        ptype = ParticleType[ptype_str]
                    except:
                        ptype = ParticleType.RSI_OVERSOLD
                        
                    particles.append(RallyParticle(
                        type=ptype,
                        val=p_dict['val'],
                        time_offset=p_dict['offset'],
                        timeframe="15m",
                        description=p_dict['desc']
                    ))
                
                seq = RallySequence(
                    particles=particles,
                    symbol=selected_coin,
                    rally_event_id=str(current_rally_obj.event_id),
                    total_duration_bars=60 # Approximate
                )
                
                # 2. Forge MasterCipher (Mock Stats for now)
                # In real flow, validate_sequence would return this
                mc = MasterCipher(
                    name=cipher_name,
                    sequence_signature=seq.key_signature,
                    template_sequence=seq,
                    conquest_score=85.0, # Placeholder
                    win_rate=0.75,
                    avg_gain_pct=15.0,
                    false_positive_rate=0.1,
                    tags=["manual_extraction"]
                )
                
                # 3. Save
                path = engine.save_master_cipher(mc)
                st.toast(f"✅ {cipher_name} başarıyla saklandı!", icon="🔐")
                st.balloons()
                st.rerun()

