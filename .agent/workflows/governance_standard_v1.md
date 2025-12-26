---
description: Governance Standard V1 - Karar Defteri ve Anayasa Mimarisi
---

# Yönetişim Standardı v1 (Governance Standard)

Bu doküman, Tezaver sistemindeki modüllerin (Foundry, Sniper, Matrix vb.) nasıl "Yönetilebilir" ve "Denetlenebilir" hale getirileceğini tanımlar. Her modül bu standarda uymalıdır.

## 1. Mimari Üçleme (The Trinity)

Her modül şu 3 bileşenden oluşmalıdır:

1.  **Anayasa (Policy File):** Kuralların ve ayarların tutulduğu JSON dosyası.
    *   Konum: `.tezaver_matrix/<module>/<module>_policy.json`
    *   Özellik: İnsan tarafından okunabilir açıklamalar (`_desc`) içermeli.
2.  **Kâtip (Audit Service):** Kararların ve işlemlerin kaydedildiği servis.
    *   Konum: `.tezaver_matrix/<module>/<module>_audit.jsonl`
    *   Format: Append-Only JSONL.
3.  **Yargıç (Configuration Service):** Anayasayı okuyan ve kodun içine enjekte eden servis.

## 2. Arayüz Standardı (UI Layout)

Her modülün UI sekmesi (Tab) şu standart yapıyı içermelidir:

### Sekme Adı: `⚖️ Karar Defteri` (<Modül Adı>)

Bu sekme altında **mutlaka** şu 3 alt sekme (Sub-tab) bulunmalıdır:

#### Tab A: `📜 Anayasa Maddeleri` (Varsayılan)
*   **İçerik:** Teknik olmayan, resmi ve hukuki bir dille yazılmış kurallar.
*   **Format:** Madde 1, Madde 1.1, Madde 1.2.a şeklinde hiyerarşik numaralandırma.
*   **Amaç:** Kullanıcının sistemin "ruhunu" ve kurallarını okuması.

#### Tab B: `⚙️ Konfigürasyon`
*   **İçerik:** Anayasadaki parametrelerin değiştirilebileceği form alanı.
*   **Bileşenler:** `st.number_input`, `st.checkbox`, `st.multiselect` vb.
*   **Amaç:** Teknik ayarların yapılması.

#### Tab C: `📙 Tutanaklar`
*   **İçerik:** Audit Service'den gelen son kayıtların tablosu.
*   **Format:** Zaman (TS) | İşlem (Action) | Konu (Subject) | Karar (Verdict) | Detay (Details).
*   **Amaç:** Sistemin ne yaptığının denetlenmesi.

### Genel UI Kuralı: Tasarım Dokümanları
*   Modüle ait teknik tasarım dokümanları (`design.md`), sayfanın **en altında**, `st.divider()` ile ayrılmış şekilde ve bir `st.expander` içinde sunulmalıdır.
*   Başlık Standardı: `📘 Teknik Tasarım (Design Doc)`
*   Dosya Yolu: Daima `Path(__file__)` referanslı "absolute path" kullanılmalıdır.

## 3. Uygulama Örneği (Python)

```python
# configuration_service.py
DEFAULT_POLICY = {
    "version": "1.0",
    "rules": {
        "threshold": 50,
        "threshold_desc": "Onay için gereken minimum skor."
    }
}

# ui_tab.py
def render_governance():
    subtab_rules, subtab_config, subtab_log = st.tabs(["📜 Anayasa Maddeleri", "⚙️ Konfigürasyon", "📙 Tutanaklar"])
    
    with subtab_rules:
        st.markdown("#### BÖLÜM 1: GENEL ESASLAR")
        st.write("**1.1. Baraj Kuralı:** Sistem, asgari **50** puan altındaki verileri reddeder.")
        
    with subtab_config:
        st.number_input("Eşik Değer (Threshold)", ...)
```

## 4. Dosya İsimlendirme

*   `.../<module>/configuration_service.py`
*   `.../<module>/audit_service.py`
*   `.../<module>_policy.json`
