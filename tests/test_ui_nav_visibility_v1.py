import pytest
import os

def test_ui_nav_visibility_perf_cost():
    """
    Verify 'Perf & Cost' is present in UI Navigation registry.
    We check the source code itself for the string presence as UI testing with Selenium is out of scope.
    """
    # 1. Check Main Panel
    main_panel_path = "src/tezaver/ui/main_panel.py"
    assert os.path.exists(main_panel_path)
    
    with open(main_panel_path, "r") as f:
        content = f.read()
        assert "Perf & Cost" in content, "Main Panel Navigation missing 'Perf & Cost'"
        assert "tezaver.bulut.ui.pages.perf_cost" in content, "Main Panel Import missing 'perf_cost'"

    # 2. Check App UI
    app_ui_path = "src/tezaver/bulut/app_ui.py"
    assert os.path.exists(app_ui_path)
    
    with open(app_ui_path, "r") as f:
        content = f.read()
        assert "Perf & Cost" in content, "App UI Sidebar missing 'Perf & Cost'"
        assert "render_perf_cost" in content, "App UI Render missing 'Perf & Cost'"

def test_page_importability():
    """
    Verify the new page module can be imported (no syntax errors).
    """
    try:
        from tezaver.bulut.ui.pages import perf_cost
        assert hasattr(perf_cost, 'render_page'), "perf_cost module missing render_page entrypoint"
    except ImportError as e:
        pytest.fail(f"Could not import perf_cost page: {e}")
