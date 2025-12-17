"""
CSS/JS-based routing helper for Matrix UI.
Hides/shows expanders based on active page without modifying Python code.
"""

import streamlit as st
import streamlit.components.v1 as components


# ALLOW mapping: page -> set of expander titles
EXPANDER_ROUTING = {
    "matrix": {
        "🔁 Live Loop Control | Canlı Döngü Kontrolü",
        "🩺 System Health Summary | Sistem Sağlık Özeti",
        "🎬 Trade Replay | İşlem Tekrarı",
        "🟢 Live Freshness / Lag | Canlı Veri Tazeliği",
        "🎮 Live Gate Status | Canlı Kapı Durumu",
    },
    "operation": {
        "🔁 Live Loop Control | Canlı Döngü Kontrolü",
        "🧭 Live Ops Console | Canlı Operasyon Konsolu",
        "📊 Cycles Report | Döngü Raporu",
    },
    "strategy": set(),  # Only Strategy Board (handled separately)
    "security": {
        "⚙️ Exchange & Arm Controls | Borsa & Yetkilendirme Kontrolleri",
        "🔐 Secrets Vault | Gizli Anahtar Kasası",
    },
    "account": {
        "🧹 Dust & Position Hygiene | Bakiye & Pozisyon Temizliği",
    },
    "events": {
        "📊 Events Explorer | Olay Gezgini",
        "📜 NDJSON Tail Viewer | NDJSON Log Görüntüleyici",
        "🧾 Last Orders (per cell) | Son Emirler (hücre bazında)",
    },
    "bundles": {
        "📦 Incident Bundles | Olay Paketi Arşivi",
    },
    "proof": {
        "✅ Closed Bar Proof | Kapalı Bar Kanıtı",
        "🔀 Closed-bar Router | Kapalı Bar Yönlendiricisi",
        "🧾 Proof+Router (E2E) | Kanıt+Yönlendirici (Uçtan Uca)",
        "🧾 Proof+Router+Cluster (E2E) | Kanıt+Yönlendirici+Küme (Uçtan Uca)",
    },
    "debug": set(),
}


def apply_expander_routing():
    """
    Apply CSS/JS routing to hide/show expanders based on active page.
    Call this at the START of _render_live_section_v2.
    """
    active_page = st.session_state.get("nav_page", "matrix")
    allowed_titles = EXPANDER_ROUTING.get(active_page, set())
    
    # Convert to JSON-safe list
    allowed_list = list(allowed_titles)
    
    # Inject JavaScript to hide/show expanders
    js_code = f"""
    <script>
    (function() {{
        // Active page and allowed expanders
        const activePage = "{active_page}";
        const allowedTitles = {allowed_list};
        
        // Wait for DOM to be ready
        function applyRouting() {{
            // Find all expander elements (Streamlit uses details/summary)
            const expanders = document.querySelectorAll('details');
            
            expanders.forEach(expander => {{
                // Get the summary text (expander title)
                const summary = expander.querySelector('summary');
                if (!summary) return;
                
                const title = summary.textContent.trim();
                
                // Check if this expander is allowed on current page
                const isAllowed = allowedTitles.some(allowed => title.includes(allowed));
                
                // Hide or show
                if (isAllowed) {{
                    expander.style.display = '';
                }} else {{
                    expander.style.display = 'none';
                }}
            }});
        }}
        
        // Apply immediately and on DOM changes
        applyRouting();
        
        // Re-apply after short delay (Streamlit re-renders)
        setTimeout(applyRouting, 100);
        setTimeout(applyRouting, 500);
        
        // Observe DOM changes
        const observer = new MutationObserver(applyRouting);
        observer.observe(document.body, {{ childList: true, subtree: true }});
    }})();
    </script>
    """
    
    # Inject the script
    components.html(js_code, height=0)
