"""
Coin Strateji Navigatörü
=========================
Coin'e özel rally tespit stratejilerini keşfedin.

Özellikler:
- Geliştirilmiş tüm stratejileri görüntüle
- Her coin için benzersiz karakteristikler ve keşifleri gör
- Performans metriklerini kontrol et (eğitim/test)
- AI içgörüleri ve önerileri oku
"""

import streamlit as st
import json
import os
from pathlib import Path

def load_coin_metadata(coin_folder):
    """Coin için metadata.json yükle."""
    # Proje root'u bul (3 seviye yukarı: ui -> tezaver -> src -> root)
    project_root = Path(__file__).resolve().parents[3]
    metadata_path = project_root / "scripts" / "coins" / coin_folder / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            return json.load(f)
    return None

def get_available_coins():
    """Metadata'sı olan coinlerin listesini al."""
    # Proje root'u bul
    project_root = Path(__file__).resolve().parents[3]
    coins_dir = project_root / "scripts" / "coins"
    
    if not coins_dir.exists():
        return []
    
    coins = []
    for folder in sorted(coins_dir.iterdir()):
        if folder.is_dir():
            metadata = load_coin_metadata(folder.name)
            if metadata:
                coins.append({
                    'folder': folder.name,
                    'symbol': metadata['symbol'],
                    'name': metadata.get('name', folder.name.upper())
                })
    return coins

def show_strategy_card(metadata):
    """Strateji bilgi kartını göster."""
    st.markdown("### 📌 Strateji Özeti")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Versiyon", metadata['strategy']['version'])
        strategy_type = metadata['strategy']['type']
        type_tr = {
            'momentum': 'Momentum',
            'momentum_volume': 'Momentum + Hacim',
            'ema_distance': 'EMA Mesafesi',
            'momentum_filtered': 'Filtrelenmiş Momentum',
            'counter_trend_dipbuying': 'Dip Alımı (Ters Trend)'
        }.get(strategy_type, strategy_type.replace('_', ' ').title())
        st.metric("Tip", type_tr)
    with col2:
        st.code(metadata['strategy']['rule'], language='python')
    
    # Açıklama ekle
    st.markdown("**📖 Açıklama:**")
    rule = metadata['strategy']['rule']
    
    # İndikatör açıklamaları
    explanations = {
        'mom_5d': '5 günlük momentum (fiyatın 5 gün öncesine göre % değişimi)',
        'mom_3d': '3 günlük momentum (fiyatın 3 gün öncesine göre % değişimi)',
        'ema_dist': 'EMA9 mesafesi (fiyatın 9-günlük üstel ortalamaya göre % uzaklığı)',
        'daily_ch': 'Günlük değişim (açılış-kapanış arası % değişim)',
        'vol_ratio': 'Hacim oranı (günlük hacim / 20 günlük ortalama hacim)',
        'no_consecutive_signals': 'Ardışık sinyal filtresi (son 2 gün içinde sinyal yoksa)'
    }
    
    # Kuralı Türkçe açıkla
    explanation_parts = []
    
    if 'mom_5d' in rule:
        if '>=' in rule:
            threshold = rule.split('>=')[1].split('and')[0].split('AND')[0].strip()
            explanation_parts.append(f"✅ **5 günlük momentum ≥ {threshold}%** → Bugünkü fiyat, 5 gün öncesine göre toplam %{threshold} veya daha fazla yükselmiş olmalı")
            explanation_parts.append(f"   📊 *Örnek: 5 gün önce $100 ise bugün ${100 + int(threshold)} olmalı*")
        elif '<=' in rule:
            threshold = rule.split('<=')[1].split('and')[0].split('AND')[0].strip()
            explanation_parts.append(f"✅ **5 günlük momentum ≤ {threshold}%** → Bugünkü fiyat, 5 gün öncesine göre toplam %{threshold} veya daha az değişmiş olmalı")
    
    if 'mom_3d' in rule:
        if '>=' in rule and 'mom_3d >=' in rule:
            threshold = [part.strip() for part in rule.split('AND') if 'mom_3d' in part][0].split('>=')[1].strip()
            explanation_parts.append(f"✅ **3 günlük momentum ≥ {threshold}%** → Bugünkü fiyat, 3 gün öncesine göre toplam %{threshold} veya daha fazla yükselmiş olmalı")
        elif '<=' in rule and 'mom_3d <=' in rule:
            threshold = [part.strip() for part in rule.split('AND') if 'mom_3d' in part][0].split('<=')[1].strip()
            explanation_parts.append(f"✅ **3 günlük momentum ≤ {threshold}%** → Bugünkü fiyat, 3 gün öncesine göre %{abs(int(threshold))} veya daha fazla DÜŞmüş olmalı (dip alımı sinyali)")
    
    if 'ema_dist' in rule:
        if '>=' in rule:
            threshold = [part.strip() for part in rule.split('AND') if 'ema_dist' in part][0].split('>=')[1].strip()
            explanation_parts.append(f"✅ Fiyat EMA9'un **{threshold}%** üzerinde olmalı")
    
    if 'daily_ch' in rule:
        if '>=' in rule and 'daily_ch >=' in rule:
            threshold = [part.strip() for part in rule.split('AND') if 'daily_ch' in part][0].split('>=')[1].strip()
            explanation_parts.append(f"✅ Günlük değişim **{threshold}%** veya daha fazla olmalı")
        elif '<=' in rule and 'daily_ch <=' in rule:
            threshold = [part.strip() for part in rule.split('AND') if 'daily_ch' in part][0].split('<=')[1].strip()
            explanation_parts.append(f"✅ Günlük değişim **{threshold}%** veya daha az olmalı (düşüş günü)")
    
    if 'vol_ratio' in rule:
        threshold = [part.strip() for part in rule.split('AND') if 'vol_ratio' in part][0].split('>=')[1].strip()
        explanation_parts.append(f"✅ Hacim normal günlerin **{threshold}x** katı olmalı")
    
    if 'no_consecutive' in rule.lower() or 'consecutive' in rule.lower():
        explanation_parts.append(f"✅ Son 2 gün içinde başka sinyal olmamalı (ardışık sinyal filtresi)")
    
    if explanation_parts:
        for part in explanation_parts:
            st.markdown(part)
    
    st.info("💡 **Rally sinyali sadece tüm koşullar sağlandığında üretilir.**")
    
def show_performance_card(metadata):
    """Performans metriklerini göster."""
    st.markdown("### 📊 Performans (Eğitim: 2023-2025)")
    
    perf = metadata['performance_train']
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Sinyal", perf['total_signals'])
    with col2:
        st.metric("Kesinlik", f"{perf['precision_pct']:.1f}%", 
                 delta="Mükemmel" if perf['precision_pct'] == 100 else None)
    with col3:
        st.metric("İsabet", perf['hits'])
    with col4:
        st.metric("Hata", perf['fails'])
    
    # Seviye dağılımı
    tiers = perf['tier_breakdown']
    st.markdown("**Seviye Dağılımı:**")
    tier_cols = st.columns(3)
    with tier_cols[0]:
        st.info(f"💎 Diamond: {tiers.get('diamond', 0)}")
    with tier_cols[1]:
        st.warning(f"🥇 Gold: {tiers.get('gold', 0)}")
    with tier_cols[2]:
        st.success(f"🥈 Silver: {tiers.get('silver', 0)}")
    
    if 'avg_gain_pct' in perf:
        st.metric("Ortalama Kazanç", f"{perf['avg_gain_pct']:.1f}%")

def show_discovery_card(metadata):
    """Benzersiz keşifleri göster."""
    st.markdown("### 🔬 Benzersiz Keşifler")
    
    discovery = metadata['discovery']
    
    # En güçlü ayırıcı
    strongest = discovery['strongest_discriminator']
    st.markdown(f"**En Güçlü Ayırıcı:** `{strongest['indicator']}`")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Rally Günleri Ort.", f"{strongest.get('rally_avg', 'N/A')}")
    with col2:
        st.metric("Normal Günler Ort.", f"{strongest.get('normal_avg', 'N/A')}")
    
    diff_pct = strongest['difference_pct']
    if diff_pct > 100000:
        st.success(f"🔥 **{diff_pct:,}% fark** - OLAĞANÜSTÜ GÜÇLÜ!")
    elif diff_pct > 10000:
        st.info(f"⚡ **{diff_pct:,}% fark** - Çok Güçlü")
    else:
        st.info(f"📈 **{diff_pct:,}% fark**")
    
    if 'rank' in strongest:
        rank_tr = strongest['rank'].replace('STRONGEST ACROSS ALL COINS', 'TÜM COİNLER ARASINDA EN GÜÇLÜ')
        st.warning(f"🏆 {rank_tr}")
    
    # Karakter tipi
    char_type = discovery['character_type']
    char_tr = {
        'Ultra-Strong Momentum': 'Ultra-Güçlü Momentum',
        'Momentum': 'Momentum',
        'Strong 5-Day Momentum': 'Güçlü 5-Gün Momentum',
        '3-Day Momentum': '3-Gün Momentum',
        'Simple Momentum': 'Basit Momentum',
        'EMA Distance Focus': 'EMA Mesafesi Odaklı',
        'Simple EMA Distance': 'Basit EMA Mesafesi',
        '3-Day Momentum with Temporal Filter': 'Zamansal Filtreli 3-Gün Momentum',
        'Reverse/Dip-Buying (UNIQUE)': 'Ters Trend/Dip Alımı (BENZERSIZ)'
    }.get(char_type, char_type)
    st.markdown(f"**Karakter Tipi:** {char_tr}")
    
    # Notlar
    if 'notes' in discovery and discovery['notes']:
        st.markdown("**Önemli Gözlemler:**")
        for note in discovery['notes']:
            st.markdown(f"- {note}")

def show_ai_insights(metadata):
    """AI içgörüleri ve önerileri göster."""
    if 'ai_insights' not in metadata:
        return
    
    st.markdown("### 🤖 AI İçgörüleri")
    
    insights = metadata['ai_insights']
    
    # Metrikler
    col1, col2, col3 = st.columns(3)
    with col1:
        clarity = insights.get('pattern_clarity', 'N/A').replace('_', ' ').title()
        clarity_tr = {
            'Exceptional': 'Mükemmel',
            'Excellent': 'Harika',
            'Good': 'İyi',
            'Unique But Rare': 'Benzersiz Ama Nadir'
        }.get(clarity, clarity)
        st.metric("Pattern Netliği", clarity_tr)
    with col2:
        simplicity = insights.get('strategy_simplicity', 'N/A').replace('_', ' ').title()
        simplicity_tr = {
            'Very Simple': 'Çok Basit',
            'Simple': 'Basit',
            'Moderate': 'Orta'
        }.get(simplicity, simplicity)
        st.metric("Strateji Basitliği", simplicity_tr)
    with col3:
        sig_count = insights.get('signal_count', 'N/A').replace('_', ' ').title()
        sig_tr = {
            'Excellent': 'Mükemmel',
            'Good': 'İyi',
            'Moderate': 'Orta',
            'Low': 'Düşük'
        }.get(sig_count, sig_count)
        st.metric("Sinyal Sayısı", sig_tr)
    
    # Öneri
    if 'recommendation' in insights:
        st.info(f"💡 **Öneri:** {insights['recommendation']}")

def show_status_card(metadata):
    """Test/prodüksiyon durumunu göster."""
    st.markdown("### 🧪 Durum")
    
    status = metadata['status']
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("✅ Eğitim Tamamlandı" if status['train_complete'] else "⏳ Eğitiliyor")
    with col2:
        if status.get('test_executed', False):
            st.success("✅ Test Tamamlandı")
        else:
            st.warning("⏳ Test Hazır (2026 saklı)")
    with col3:
        if status.get('production_ready', False):
            st.success("✅ Prod. Hazır")
        else:
            st.info("🔧 Geliştirme")

def main():
    # Version 2.1 - Türkçe UI
    st.title("🎯 Coin Strateji Navigatörü")
    st.markdown("*%100 kesinlikle coin'e özel rally tespit stratejilerini keşfedin*")
    st.markdown("---")
    
    # Mevcut coinleri al
    coins = get_available_coins()
    
    if not coins:
        st.error("Coin stratejisi bulunamadı. Lütfen önce analiz scriptlerini çalıştırın.")
        st.info(f"Beklenen yol: {Path(__file__).resolve().parents[3] / 'scripts' / 'coins'}")
        return
    
    # Ana alanda coin seçimi
    st.markdown("### 🪙 Coin Seçin")
    coin_options = {f"{c['symbol']} - {c['name']}": c['folder'] for c in coins}
    
    col1, col2 = st.columns([2, 3])
    with col1:
        selected = st.selectbox("Keşfetmek için bir coin seçin:", list(coin_options.keys()), label_visibility="collapsed")
    
    if not selected:
        st.info("Lütfen dropdown'dan bir coin seçin.")
        return
    
    # Seçilen coin metadata'sını yükle
    coin_folder = coin_options[selected]
    metadata = load_coin_metadata(coin_folder)
    
    if not metadata:
        st.error(f"{selected} için metadata yüklenemedi")
        return
    
    # Ana alanda hızlı istatistikler (yatay)
    with col2:
        stat_cols = st.columns(3)
        with stat_cols[0]:
            st.metric("Sinyaller", metadata['performance_train']['total_signals'], help="Eğitim verisindeki toplam sinyal")
        with stat_cols[1]:
            st.metric("Kesinlik", f"{metadata['performance_train']['precision_pct']}%", help="Sinyal doğruluğu")
        with stat_cols[2]:
            strategy_type = metadata['strategy']['type']
            type_tr = {
                'momentum': 'Momentum',
                'momentum_volume': 'Mom.+Hacim',
                'ema_distance': 'EMA Mesafe',
                'momentum_filtered': 'Filtre Mom.',
                'counter_trend_dipbuying': 'Dip Alımı'
            }.get(strategy_type, strategy_type.replace('_', ' ').title())
            st.metric("Tip", type_tr, help="Strateji kategorisi")
    
    st.markdown("---")
    
    # Coin başlığını göster
    st.markdown(f"## {metadata['symbol']} - {metadata.get('name', 'Bilinmeyen')}")
    
    # DG Rally sayısını hesapla (Diamond + Gold tier breakdown'dan)
    tiers = metadata['performance_train']['tier_breakdown']
    captured_dg = tiers.get('diamond', 0) + tiers.get('gold', 0)
    total_rallies = sum(tiers.values())
    
    # Toplam DG rally sayısı (metadata'dan)
    total_dg = metadata.get('total_dg_rallies', captured_dg)
    coverage_pct = (captured_dg / total_dg * 100) if total_dg > 0 else 0
    
    # Başlık altında bilgi satırı
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.caption(f"📅 Oluşturulma: {metadata['created_date']} | Versiyon: {metadata['version']}")
    with col_info2:
        st.caption(f"🎓 Eğitim Dönemi: 2023-2025")
    with col_info3:
        st.caption(f"💎 **DG Rally Kapsama: {captured_dg}/{total_dg}** ({coverage_pct:.0f}%) | Toplam Sinyal: {total_rallies}")

    
    # Kartları göster
    show_strategy_card(metadata)
    st.divider()
    
    show_performance_card(metadata)
    st.divider()
    
    show_discovery_card(metadata)
    st.divider()
    
    show_ai_insights(metadata)
    st.divider()
    
    show_status_card(metadata)

if __name__ == "__main__":
    main()
