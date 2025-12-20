# Tezaver Bulut - Register Pages
"""
Registration entrypoint for all Bulut UI pages.
Imports each page module and calls the registry.
"""
from tezaver.bulut.ui.contracts.page_registry import Registry, BulutPage

def register_all_pages():
    """
    Import and register all known UI pages.
    """
    # 1. Command Center
    try:
        from tezaver.bulut.ui.pages import command_center
        # Assuming command_center handles its own registration on import OR we register it here.
        # Plan: Pages should export their 'BULUT_PAGE_DEF' or we manually construct here?
        # Better: Pages register themselves? 
        # User requirement: "ONE PLACE" -> register_pages.py call register_page(...)
        
        # So we import the render_fn from pages and register here.
        Registry.register_page(BulutPage(
            id="command_center",
            title_tr="Komuta Merkezi",
            category_tr="Operasyon",
            order=10,
            render_fn=command_center.render_page,
            requires_backend=True,
            requires_ops_token=True # Maybe? It has ops actions
        ))
    except ImportError as e:
        print(f"Warning: Could not load command_center: {e}")
    except Exception as e:
         print(f"Warning: Error registering command_center: {e}")

    # 2. Daily Ops
    try:
        from tezaver.bulut.ui.pages import daily_ops
        Registry.register_page(BulutPage(
            id="daily_ops",
            title_tr="Günlük Operasyon",
            category_tr="Operasyon",
            order=20,
            render_fn=daily_ops.render_page,
            requires_backend=True
        ))
    except ImportError: pass

    # 3. Live Charts
    try:
        from tezaver.bulut.ui.pages import live_charts
        Registry.register_page(BulutPage(
            id="live_charts",
            title_tr="Canlı Grafikler",
            category_tr="Ticaret",
            order=30,
            render_fn=live_charts.render_page,
            requires_backend=True
        ))
    except ImportError: pass

    # 4. Rules Editor
    try:
        from tezaver.ui.subpages import rules_editor
        # rules_editor might need a wrapper if it doesn't take 'ctx'
        # Creating a lambda wrapper if signature mismatch?
        # Ideally we refactor rules_editor to accept ctx or optional ctx.
        if hasattr(rules_editor, 'render_rules_editor'):
             # Standardizing: It usually accepted 'api_base' or nothing.
             # We'll check the refactor.
             Registry.register_page(BulutPage(
                id="rules_editor",
                title_tr="Kural Editörü",
                category_tr="Geliştirici",
                order=90,
                render_fn=lambda ctx: rules_editor.render_rules_editor(ctx.config.api_base_url if hasattr(ctx, 'config') else "http://localhost:8000"),
                requires_backend=True
            ))
    except ImportError: pass

    # 5. Test Report
    try:
        from tezaver.bulut.ui.pages import test_report
        Registry.register_page(BulutPage(
            id="test_report",
            title_tr="Test Raporu",
            category_tr="Geliştirici",
            order=95,
            render_fn=test_report.render_page,
            requires_backend=False # Ideally purely static xml read?
        ))
    except ImportError: pass
    
    # 6. Perf & Cost
    try:
        from tezaver.bulut.ui.pages import perf_cost
        Registry.register_page(BulutPage(
            id="perf_cost",
            title_tr="Perf & Cost",
            category_tr="Performans",
            order=40,
            render_fn=perf_cost.render_page,
            requires_backend=True,
            requires_ops_token=True
        ))
    except ImportError: pass
    
    # 7. Intel Manager
    try:
        from tezaver.bulut.ui.pages import intel_manager
        Registry.register_page(BulutPage(
            id="intel_manager",
            title_tr="Intel Yönetimi",
            category_tr="Intel",
            order=50,
            render_fn=intel_manager.render_page,
            requires_backend=True
        ))
    except ImportError: pass

    # 8. Journal
    try:
        from tezaver.bulut.ui.pages import journal
        Registry.register_page(BulutPage(
            id="journal",
            title_tr="Seyir Defteri",
            category_tr="Operasyon",
            order=25,
            render_fn=journal.render_page,
            requires_backend=True
        ))
    except ImportError: pass
    
    # 9. Explorer
    try:
        from tezaver.bulut.ui.pages import explorer
        Registry.register_page(BulutPage(
            id="explorer",
            title_tr="Explorer",
            category_tr="Adli İnceleme",
            order=60,
            render_fn=explorer.render_page,
            requires_backend=True
        ))
    except ImportError: pass
