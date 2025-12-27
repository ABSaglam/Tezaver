"""
Alchemist Tab - Simyacı Arketip Keşfi
=======================================

UI for browsing bundles and running clustering analysis to discover Archetypes.
"""

import streamlit as st
import pandas as pd
import importlib
from pathlib import Path

from tezaver.foundry.bundle_index import scan_bundles
import tezaver.foundry.clustering_service
import tezaver.foundry.archetype_storyteller
import tezaver.foundry.configuration_service
importlib.reload(tezaver.foundry.clustering_service)
importlib.reload(tezaver.foundry.archetype_storyteller)
importlib.reload(tezaver.foundry.configuration_service)

from tezaver.foundry.clustering_service import ClusteringService
from tezaver.foundry.archetype_storyteller import ArchetypeStoryteller
from tezaver.foundry.configuration_service import ConfigurationService
from tezaver.foundry.audit_service import AuditService


@st.cache_data(ttl=60)
def cached_scan_bundles_for_alchemist():
    """Cached bundle scanning for Alchemist."""
    return scan_bundles()



def render_alchemist_page():
    """Render The Alchemist (Clustering) Page."""
    st.title("🧪 Simyacı (Arketip Keşfi)")

    # Tabs
    tab_sim, tab_gov = st.tabs(["⚗️ Simyacı", "⚖️ Karar Defteri"])

    with tab_sim:
        _render_alchemist_core()

    with tab_gov:
        _render_governance_tab()

def _render_alchemist_core():
    # Content migrated from original render_alchemist_page
    st.info("Bu modül, tekil paketleri analiz ederek ortak desenleri (Arketipleri/Ruhları) ortaya çıkarır.")
    
    # 1. Select Cohort
    df_bundles = cached_scan_bundles_for_alchemist()
    
    if not df_bundles.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            symbols = sorted(df_bundles["symbol"].unique().tolist())
            index = 0
            # Try to preserve selection if possible (using session state keys unique to this page)
            if "alc_sym" in st.session_state and st.session_state["alc_sym"] in symbols:
                index = symbols.index(st.session_state["alc_sym"])
            sel_sym = st.selectbox("Sembol (Coin)", symbols, index=index, key="alc_sym")
            
        with c2:
            timeframes = sorted(df_bundles["timeframe"].unique().tolist())
            index = 0
            if "alc_tf" in st.session_state and st.session_state["alc_tf"] in timeframes:
                index = timeframes.index(st.session_state["alc_tf"])
            sel_tf = st.selectbox("Zaman Dilimi (TF)", timeframes, index=index, key="alc_tf")
            
        with c3:
            clusters_n = st.slider("Arketip Sayısı (K)", 2, 5, 3, key="alc_k")
            
        # Filter Cohort
        cohort = df_bundles[
            (df_bundles["symbol"] == sel_sym) & 
            (df_bundles["timeframe"] == sel_tf)
        ]
        
        st.markdown(f"**Havuz:** {len(cohort)} adet paket var.")
        
        if len(cohort) < 3:
            st.error("Analiz için en az 3 paket gerekli.")
            
        elif st.button("⚗️ Simyayı Başlat (Analyze)", type="primary"):
            with st.spinner("Damıtılıyor... (Distilling Essence)"):
                mixer = ClusteringService()
                storyteller = ArchetypeStoryteller()
                
                # Run Clustering
                result = mixer.cluster_bundles(cohort, n_clusters=clusters_n)
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    # Display Archetypes
                    st.success("✨ Keşif Tamamlandı!")
                    
                    centroids = result["centroids"]
                    cols = st.columns(len(centroids))
                    
                    for i, cent in enumerate(centroids):
                        story = storyteller.tell_story(cent)
                        
                        with cols[i]:
                            st.markdown(f"#### {story['label']}")
                            st.caption(f"Risk: {story['risk_profile']}")
                            st.markdown(f"**{cent['count']}** Üye")
                            
                            # Clamp values to [0.0, 1.0]
                            gain_prog = min(1.0, max(0.0, cent['avg_gain'] / 50.0)) # Scale to 50% max
                            dur_prog = min(1.0, max(0.0, cent['avg_duration'] / 100.0)) # Scale to 100 bars max
                            
                            st.progress(gain_prog, text=f"Gain: {cent['avg_gain']:.1f}%") 
                            st.progress(dur_prog, text=f"Dur: {int(cent['avg_duration'])} bars")
                            
                            st.info(story['description'])
                            
                            with st.expander("Üye Listesi"):
                                st.write(cent['member_ids'])
    else:
        st.warning("Analiz için veri yok. Önce paketleme yapın.")
        
    st.divider()
    # Documentation link logic (adapted path)
    with st.expander("📘 Teknik Tasarım (Design Doc) v1.1"):
        try:
            # tezaver/ui/alchemist_tab.py -> parent=tezaver/ui -> parent.parent=tezaver
            base_dir = Path(__file__).resolve().parent.parent
            doc_path = base_dir / "foundry/docs/archetype_design.md"
            if doc_path.exists():
                st.markdown(doc_path.read_text(encoding="utf-8"))
            else:
                st.warning(f"Tasarım dokümanı bulunamadı: {doc_path}")
        except Exception as e:
            st.error(f"Doküman okunamadı: {e}")

def _render_governance_tab():
    """Render Governance (Karar Defteri) Tab - Migrated from Foundry."""
    config = ConfigurationService()
    audit = AuditService()
    
    subtab_rules, subtab_config, subtab_log = st.tabs(["📜 Anayasa Maddeleri", "⚙️ Konfigürasyon", "📙 Tutanaklar"])
    
    qc = config.get_qc_rules()
    pkg = config.get_packaging_rules()
    alc = config.get_alchemist_rules()

    with subtab_rules:
        st.markdown("### Dökümhane Anayasası")
        st.info("İşbu Anayasa, Revize Stüdyosu'ndan çıkan işlerin denetim ve üretim süreçlerini düzenler.")
        
        # Article 1: QC
        st.markdown("#### BÖLÜM 1: KALİTE VE DENETİM")
        st.markdown("**Madde 1 - Kabul Şartları ve Puanlama**")
        st.write(f"""
        **1.1. Puanlama Esası:** Herbir revizyon paketi, QC Gate v1 denetim motoru tarafından 100 üzerinden puanlanır. Onay için asgari **{qc.get('min_score', 60)}** puan gereklidir.
        
        **1.2. Kırmızı Çizgiler (Zorunlu Denetimler):** Aşağıdaki denetimlerden herhangi birinin başarısız olması durumunda, puan dikkate alınmaksızın paket reddedilir:
        *   a) **QC-010:** Fiyat geçmişi eksiksiz olmalı.
        *   b) **QC-040:** Olay, ana veri setinde (Rally Dataset) kayıtlı olmalı.
        *   c) **QC-050:** Giriş ve Olay zamanları mantıksal olarak tutarlı olmalı.
        
        **1.3. Denetim Modu:** {'Sistem **Katı Mod (Strict Mode)** ile çalışır; en ufak bir uyumsuzluk reddine sebebiyet verir.' if qc.get('strict_mode') else 'Sistem **Esnek Mod** ile çalışır; kritik olmayan hatalarda puan yeterliyse geçiş izni verilir.'}
        """)
        
        st.divider()
        
        # Article 2: Packaging
        st.markdown("#### BÖLÜM 2: ÜRETİM VE SEVKİYAT")
        st.markdown("**Madde 2 - Paketleme Standartları**")
        st.write(f"""
        **2.1. Yetkilendirilmiş Sınıflar:** Yalnızca **{', '.join(pkg.get('allowed_tiers', []))}** sertifika sınıfına sahip varlıklar üretim hattına alınır. Diğer sınıflar işleme kapatılmıştır.
        
        **2.2. Üretim Kotaları:** Kaynak verimliliği adına, her bir parite (Coin) ve zaman dilimi (TF) kombinasyonu için azami **{pkg.get('max_bundles_per_coin', 5)}** adet paket üretilmesine izin verilir.
        
        **2.3. İsimlendirme ve Etiketleme:** Üretilen tüm paketler, izlenebilirliği sağlamak amacıyla istisnasız `{pkg.get('naming_convention', 'STANDARD_V1')}` standardına uygun olarak etiketlenir.
        """)
        
        st.divider()
        
        # Article 3: Alchemy
        st.markdown("#### BÖLÜM 3: SİMYA VE KEŞİF (AR-GE)")
        st.markdown("**Madde 3 - Arketip Damıtma**")
        st.write(f"""
        **3.1. Havuz Büyüklüğü:** İstatistiksel anlamlılık için en az **{alc.get('min_cohort_size', 3)}** adet paket biriktirilmeden damıtma işlemi yapılamaz.
        
        **3.2. DNA Analizi:** Arketiplerin ayrıştırılmasında şu öznitelikler esas alınır: `{', '.join(alc.get('features', []))}`
        """)
        
    with subtab_config:
        st.subheader("⚙️ Sistem Ayarları")
        st.caption(f"Sürüm: {config.get_version()}")
        
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("🛡️ Kalite Kontrol (QC)", expanded=True):
                 if "description" in qc: st.caption(qc["description"])
                 st.number_input("Min Geçme Puanı", value=qc.get("min_score", 60), disabled=True)
                 st.checkbox("Katı Mod (Strict)", value=qc.get("strict_mode", True), disabled=True)
                 st.multiselect("Zorunlu Kontroller", options=qc.get("mandatory_checks", []), default=qc.get("mandatory_checks", []), disabled=True)
                 
            with st.expander("⚗️ Simyacı Kuralları", expanded=True):
                 if "description" in alc: st.caption(alc["description"])
                 st.number_input("Min Havuz Boyutu", value=alc.get("min_cohort_size", 3), disabled=True)
                 st.number_input("Varsayılan K", value=alc.get("default_k", 3), disabled=True)
        
        with c2:
            with st.expander("📦 Paketleme Kuralları", expanded=True):
                 if "description" in pkg: st.caption(pkg["description"])
                 st.multiselect("İzin Verilen Tier'lar", options=pkg.get("allowed_tiers", []), default=pkg.get("allowed_tiers", []), disabled=True)
                 st.number_input("Max Paket / Coin", value=pkg.get("max_bundles_per_coin", 5), disabled=True)


    with subtab_log:
        st.subheader("📙 Tutanaklar (Audit Log)")
        logs = audit.read_recent_logs(limit=100)
        
        if logs:
            df_logs = pd.DataFrame(logs)
            st.dataframe(
                df_logs[["ts", "action", "subject", "verdict", "details"]],
                use_container_width=True,
                height=500
            )
        else:
            st.info("Henüz kayıt bulunmuyor. İşlem yapıldığında burada görünecektir.")
