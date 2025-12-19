# Tezaver Bulut - Daily Ops UI Visibility Test
"""
Smoke tests to verify Daily Ops is visible in UI navigation.
"""
import pytest


def test_daily_ops_render_function_importable():
    """Test that the Daily Ops render function can be imported."""
    from tezaver.bulut.ui.pages.daily_ops import render_daily_ops_page
    
    assert callable(render_daily_ops_page), "render_daily_ops_page should be callable"


def test_daily_ops_in_cloud_menu_options():
    """Test that Daily Ops is in the cloud mode menu options."""
    # Read main_panel.py and check menu_options contains Daily Ops
    from pathlib import Path
    
    main_panel_path = Path(__file__).parents[3] / "ui" / "main_panel.py"
    
    if main_panel_path.exists():
        content = main_panel_path.read_text()
        assert "Daily Ops" in content, "Daily Ops should be in main_panel.py"
        assert "menu_options" in content, "menu_options should be in main_panel.py"


def test_daily_ops_in_app_ui_navigation():
    """Test that Daily Ops is in standalone app_ui.py navigation."""
    from pathlib import Path
    
    app_ui_path = Path(__file__).parents[2] / "app_ui.py"
    
    if app_ui_path.exists():
        content = app_ui_path.read_text()
        assert "Daily Ops" in content, "Daily Ops should be in app_ui.py navigation"
        assert "render_daily_ops_page" in content, "render_daily_ops_page should be imported in app_ui.py"


def test_daily_ops_page_has_render_function():
    """Test that daily_ops.py has the expected render function."""
    from tezaver.bulut.ui.pages import daily_ops
    
    assert hasattr(daily_ops, "render_daily_ops_page"), "daily_ops module should have render_daily_ops_page"
