# Tezaver Bulut - Registry Contract Tests
import pytest
from tezaver.bulut.ui.contracts.page_registry import Registry, BulutPage

def test_registry_mechanics():
    """Test basic registry operations."""
    Registry.reset()
    
    # 1. Register valid page
    p1 = BulutPage(
        id="test_page",
        title_tr="Test Sayfası",
        category_tr="Test",
        order=1,
        render_fn=lambda ctx: None
    )
    Registry.register_page(p1)
    
    assert Registry.get_page("test_page") == p1
    assert len(Registry.list_pages()) == 1
    
    # 2. Duplicate ID enforcement
    with pytest.raises(ValueError):
        Registry.register_page(p1)
        
    # 3. Category filtering
    p2 = BulutPage(
        id="ops_page",
        title_tr="Ops",
        category_tr="Operasyon",
        order=2,
        render_fn=lambda ctx: None
    )
    Registry.register_page(p2)
    
    ops_pages = Registry.list_pages(category="Operasyon")
    assert len(ops_pages) == 1
    assert ops_pages[0].id == "ops_page"

def test_registry_integration_contract():
    """
    Enforce that register_all_pages() populates the registry with required pages.
    This test will FAIL until Step C is implemented.
    """
    Registry.reset()
    
    try:
        from tezaver.bulut.ui.register_pages import register_all_pages
        register_all_pages()
    except ImportError:
        pytest.fail("register_pages module not found (Step C pending)")
    except Exception as e:
        pytest.fail(f"register_all_pages failed: {e}")
        
    # Required pages
    required_ids = [
        "command_center",
        "live_charts", 
        "rules_editor",
        "test_report",
        "daily_ops"
    ]
    
    pages = {p.id: p for p in Registry.list_pages()}
    
    for rid in required_ids:
        assert rid in pages, f"Required page '{rid}' not registered!"
        p = pages[rid]
        assert p.title_tr, f"Page '{rid}' must have title_tr"
        assert p.category_tr, f"Page '{rid}' must have category_tr"
        assert callable(p.render_fn), f"Page '{rid}' must have callable render_fn"
