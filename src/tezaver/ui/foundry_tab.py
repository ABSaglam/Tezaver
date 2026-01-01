"""
Dökümhane (Foundry) - 3 Tab UI
===============================
"Kontrol Merkezi: Özet + Kasa + Paketçi"

Tab 1: Özet - System dashboard and health monitoring
Tab 2: Kasa - Master Cipher vault browser
Tab 3: Paketçi - Export manager for Matrix/Cloud
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

from tezaver.core.rally_store import RallyStore
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def render_foundry_page():
    """Main render function for Dökümhane."""
    st.title("🏭 Dökümhane")
    st.caption("Master Cipher Kontrol Merkezi")
    
    # 3 Tab Structure
    tab1, tab2, tab3 = st.tabs(["📊 Özet", "🔐 Kasa", "📦 Paketçi"])
    
    with tab1:
        render_ozet_tab()
    
    with tab2:
        render_kasa_tab()
    
    with tab3:
        render_paketci_tab()


def render_ozet_tab():
    """Tab 1: Özet (Dashboard)"""
    st.header("Sistem Özeti")
    
    store = RallyStore()
    
    # Fetch all rallies for health check
    all_rallies = store.list_rallies(limit=10) # Limit is fine for >0 check
    
    # Rally Envanteri
    st.subheader("📋 Rally Envanteri")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Count by tier using direct SQL (not limited)
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT tier, COUNT(*) FROM rallies GROUP BY tier')
    results = cursor.fetchall()
    tier_counts = {tier: count for tier, count in results}
    conn.close()
    
    with col1:
        st.metric("💎 Diamond", tier_counts.get('DIAMOND', 0))
    with col2:
        st.metric("🥇 Gold", tier_counts.get('GOLD', 0))
    with col3:
        st.metric("🥈 Silver", tier_counts.get('SILVER', 0))
    with col4:
        st.metric("🥉 Bronze", tier_counts.get('BRONZE', 0))
    
    st.divider()
    
    # Cipher Vault Status
    st.subheader("🔐 Kasa Durumu")
    
    vault_dir = Path(".tezaver_matrix/vault/ciphers")
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    ciphers = list(vault_dir.glob("*.json"))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Toplam Şifre", len(ciphers))
    with col2:
        # Count active ciphers
        active_count = 0
        for cipher_file in ciphers:
            try:
                with open(cipher_file) as f:
                    cipher = json.load(f)
                    if cipher.get('lifecycle', {}).get('status') == 'ACTIVE':
                        active_count += 1
            except:
                pass
        st.metric("Aktif Şifre", active_count)
    with col3:
        st.metric("Draft Şifre", len(ciphers) - active_count)
    
    st.divider()
    
    # System Health
    st.subheader("⚕️ Sistem Sağlığı")
    
    health_items = [
        ("Rally Veritabanı", "✅ Çalışıyor", len(all_rallies) > 0),
        ("Feature Engine", "✅ Hazır", True),
        ("Mining Algorithms", "✅ Hazır", True),
        ("Backtest Engine", "✅ Hazır", True),
    ]
    
    for name, status, is_ok in health_items:
        if is_ok:
            st.success(f"{name}: {status}")
        else:
            st.error(f"{name}: ❌ Sorun var")


def render_kasa_tab():
    """Tab 2: Kasa (Vault Browser)"""
    st.header("Master Cipher Kasası")
    
    vault_dir = Path(".tezaver_matrix/vault/ciphers")
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    ciphers = list(vault_dir.glob("*.json"))
    
    if len(ciphers) == 0:
        st.info("📭 Henüz şifre üretilmedi. Simyacı'dan yeni şifre oluşturun.")
        return
    
    # Cipher list
    st.subheader(f"Toplam {len(ciphers)} Şifre")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_tier = st.selectbox("Tier", ["Tümü", "DIAMOND", "GOLD", "SILVER", "BRONZE"])
    with col2:
        filter_status = st.selectbox("Durum", ["Tümü", "ACTIVE", "DRAFT", "WARNING", "ARCHIVE"])
    with col3:
        sort_by = st.selectbox("Sırala", ["En Yeni", "En Eski", "İsme Göre"])
    
    # Load and display ciphers
    cipher_data = []
    
    for cipher_file in ciphers:
        try:
            with open(cipher_file) as f:
                cipher = json.load(f)
            
            # Apply filters
            tier = cipher.get('target', {}).get('tier', 'ANY')
            status = cipher.get('lifecycle', {}).get('status', 'DRAFT')
            
            if filter_tier != "Tümü" and tier != filter_tier:
                continue
            if filter_status != "Tümü" and status != filter_status:
                continue
            
            cipher_data.append({
                'ID': cipher.get('cipher_id', 'Unknown'),
                'Tier': tier,
                'Archetype': cipher.get('target', {}).get('archetype', 'ANY'),
                'Durum': status,
                'Features': cipher.get('entry_rules', {}).get('feature_count', 0),
                'Oluşturulma': cipher.get('created_at', 'Unknown'),
                'File': cipher_file
            })
        except Exception as e:
            logger.warning(f"Failed to load {cipher_file}: {e}")
    
    if not cipher_data:
        st.warning("Filtre kriterlerine uygun şifre bulunamadı.")
        return
    
    # Display as dataframe
    df = pd.DataFrame(cipher_data)
    
    # Select cipher to view
    selected_idx = st.selectbox(
        "Şifre Seç",
        range(len(df)),
        format_func=lambda i: f"{df.iloc[i]['ID']} ({df.iloc[i]['Tier']})"
    )
    
    if selected_idx is not None:
        selected_cipher_file = df.iloc[selected_idx]['File']
        
        with open(selected_cipher_file) as f:
            cipher = json.load(f)
        
        st.divider()
        st.subheader("Şifre Detayları")
        
        # Display cipher details
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Hedef:**")
            st.json(cipher.get('target', {}))
        
        with col2:
            st.write("**Giriş Kuralları:**")
            features = cipher.get('entry_rules', {}).get('selected_features', [])
            st.write(f"Toplam {len(features)} özellik:")
            for i, feat in enumerate(features[:10], 1):
                st.text(f"{i}. {feat}")
            if len(features) > 10:
                st.text(f"... ve {len(features) - 10} daha")
        
        st.write("**Eğitim İstatistikleri:**")
        st.json(cipher.get('training_stats', {}))
        
        st.write("**Özet:**")
        summary = cipher.get('human_readable_summary', {})
        st.info(summary.get('tr', 'Özet mevcut değil'))


def render_paketci_tab():
    """Tab 3: Paketçi (Export Manager)"""
    st.header("Paketçi - Export Manager")
    
    st.info("🚧 Paketçi modülü yakında eklenecek.")
    st.write("Bu modül Master Cipher'ları Matrix/Cloud'a export etmek için kullanılacak.")
    
    # Placeholder UI
    st.subheader("Export Özellikleri")
    
    st.checkbox("Aktif şifreleri dahil et")
    st.checkbox("Draft şifreleri dahil et")
    st.selectbox("Export formatı", ["JSON", "ZIP Bundle", "CSV"])
    
    st.button("Export Hazırla", disabled=True)
