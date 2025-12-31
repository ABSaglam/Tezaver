"""
Simyacı UI - Master Cipher Generation Interface
================================================
"DNA Madenciliği Kontrol Paneli"

User can:
1. Select target (tier, archetype, coin class, timeframe)
2. Choose mining algorithm
3. Review rally count
4. Generate Master Cipher
5. View generation status
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import json

from tezaver.core.rally_store import RallyStore
from tezaver.core.logging_utils import get_logger
from tezaver.smyrna.cipher_generator import CipherGenerator

logger = get_logger(__name__)


def render_alchemist_page():
    """Main Simyacı UI."""
    st.title("🧪 Simyacı 3.0")
    st.caption("Master Cipher DNA Madenciliği")
    
    st.divider()
    
    # === SECTION 1: TARGET SELECTION ===
    st.subheader("🎯 Hedef Seçimi")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        target_tier = st.selectbox(
            "Tier",
            ["Tümü", "DIAMOND", "GOLD", "SILVER", "BRONZE"],
            help="Hangi tier rallyleri için şifre üretilsin?"
        )
    
    with col2:
        target_archetype = st.selectbox(
            "Archetype",
            ["Tümü", "PHOENIX", "GRIND", "GUILLOTINE", "SUPERNOVA", "NINJA", "SURFER"],
            help="Hangi archetype için şifre üretilsin?"
        )
    
    with col3:
        target_coin_class = st.selectbox(
            "Coin Sınıfı",
            ["Tümü", "A (Aristocrat)", "B (Standard)", "C (Aggressive)"],
            help="Hangi coin karakteri için?"
        )
    
    with col4:
        target_timeframe = st.selectbox(
            "Timeframe",
            ["15m", "1h", "4h"],
            help="Hangi zaman dilimi?"
        )
    
    # Parse selections
    tier_filter = None if target_tier == "Tümü" else target_tier
    archetype_filter = None if target_archetype == "Tümü" else target_archetype
    
    coin_class_filter = None
    if target_coin_class != "Tümü":
        coin_class_filter = target_coin_class[0]  # Extract A, B, or C
    
    st.divider()
    
    # === SECTION 2: ALGORITHM SELECTION ===
    st.subheader("⚙️ Mining Algoritması")
    
    algorithm = st.radio(
        "Algoritma Seç",
        ["ensemble", "backward", "genetic"],
        format_func=lambda x: {
            "ensemble": "🎯 Ensemble (Önerilen) - BE + GA kombinasyonu",
            "backward": "🔍 Backward Elimination - Feature elimination",
            "genetic": "🧬 Genetic Algorithm - Evolutionary search"
        }[x],
        help="Ensemble tüm algoritmaları birleştirir (en güvenilir)"
    )
    
    st.divider()
    
    # === SECTION 3: RALLY PREVIEW ===
    st.subheader("📊 Rally Önizleme")
    
    store = RallyStore()
    
    # Load ALL rallies - then filter
    # More efficient than limiting before filtering (might miss target rallies)
    all_rallies = store.list_rallies(limit=100000)  # Large limit to get all
    
    matching_rallies = []
    for rally in all_rallies:
        # Apply filters
        if tier_filter and rally.get('tier') != tier_filter:
            continue
        
        rev_data = rally.get('rev_data') or {}
        
        if archetype_filter and rev_data.get('archetype') != archetype_filter:
            continue
        
        if coin_class_filter and rev_data.get('coin_class') != coin_class_filter:
            continue
        
        if rally.get('timeframe') != target_timeframe:
            continue
        
        # NOTE: Not filtering by APPROVED status yet
        # Many rallies don't have rev_data populated yet
        # TODO: Re-enable when rev_data is consistently populated
        # if rev_data.get('status') != 'APPROVED':
        #     continue
        
        matching_rallies.append(rally)
    
    rally_count = len(matching_rallies)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Eşleşen Rally", rally_count)
    
    with col2:
        min_required = 30
        is_sufficient = rally_count >= min_required
        status = "✅ Yeterli" if is_sufficient else "⚠️ Yetersiz"
        st.metric("Durum", status)
    
    with col3:
        st.metric("Minimum Gerekli", min_required)
    
    if rally_count > 0:
        with st.expander(f"Rally Detayları ({rally_count} rally)"):
            rally_df = pd.DataFrame([
                {
                    'Symbol': r['symbol'],
                    'Tier': r.get('tier', 'N/A'),
                    'Archetype': (r.get('rev_data') or {}).get('archetype', 'N/A'),
                    'Gain': f"{(r.get('raw_data') or {}).get('future_max_gain_pct', 0):.1f}%"
                }
                for r in matching_rallies[:50]  # Show first 50
            ])
            st.dataframe(rally_df, use_container_width=True)
    
    st.divider()
    
    # === SECTION 4: GENERATION ===
    st.subheader("🔬 Şifre Üretimi")
    
    if rally_count < 10:
        st.error("❌ Şifre üretmek için en az 10 rally gerekli!")
        st.info("Lütfen farklı filtreler deneyin veya daha fazla rally onaylayın.")
        return
    
    if rally_count < 30:
        st.warning("⚠️ 30'dan az rally ile sonuçlar güvenilir olmayabilir!")
    
    # Generation button
    col1, col2 = st.columns([1, 3])
    
    with col1:
        generate_btn = st.button(
            "🚀 Şifre Üret",
            type="primary",
            use_container_width=True
        )
    
    with col2:
        st.caption(f"Hedef: {target_tier} / {target_archetype} / {target_coin_class} / {target_timeframe}")
    
    # Generation logic
    if generate_btn:
        with st.spinner("🧬 DNA analizi yapılıyor..."):
            try:
                generator = CipherGenerator(algorithm=algorithm)
                
                cipher = generator.generate_cipher(
                    tier=tier_filter,
                    archetype=archetype_filter,
                    coin_class=coin_class_filter,
                    timeframe=target_timeframe
                )
                
                st.success("✅ Master Cipher başarıyla oluşturuldu!")
                
                # Display result
                st.subheader("Üretilen Şifre")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Şifre ID:**")
                    st.code(cipher['cipher_id'])
                    
                    st.write("**Seçilen Özellikler:**")
                    features = cipher['entry_rules']['selected_features']
                    st.write(f"Toplam {len(features)} feature:")
                    for i, feat in enumerate(features[:10], 1):
                        st.text(f"{i}. {feat}")
                    if len(features) > 10:
                        st.text(f"... ve {len(features) - 10} daha")
                
                with col2:
                    st.write("**Eğitim Detayları:**")
                    stats = cipher['training_stats']
                    st.metric("Eğitim Rally Sayısı", stats['rally_count'])
                    st.metric("Pozitif Oran", f"{stats['positive_ratio']*100:.1f}%")
                    st.metric("Feature Havuzu", stats['feature_pool_size'])
                
                st.info(f"💾 Şifre vault'a kaydedildi: `.tezaver_matrix/vault/ciphers/{cipher['cipher_id']}.json`")
                
                st.write("**Özet:**")
                st.success(cipher['human_readable_summary']['tr'])
                
            except Exception as e:
                st.error(f"❌ Şifre üretimi başarısız: {e}")
                logger.error(f"Cipher generation failed: {e}", exc_info=True)
