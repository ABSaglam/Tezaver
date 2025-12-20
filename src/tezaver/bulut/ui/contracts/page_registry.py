# Tezaver Bulut UI - Page Registry Contract
from dataclasses import dataclass
from typing import Callable, Optional, List, Dict

# Type alias for context (to avoid circular imports, usually Any or specific class)
BulutUiContext = "BulutUiContext" 

@dataclass
class BulutPage:
    """Definition of a UI page in Tezaver Bulut."""
    id: str
    title_tr: str
    category_tr: str  # e.g. "Ops", "Risk", "Perf", "Trading"...
    order: int
    render_fn: Callable[[BulutUiContext], None]
    requires_backend: bool = True
    requires_ops_token: bool = False

class Registry:
    """Singleton registry for all Bulut UI pages."""
    _pages: Dict[str, BulutPage] = {}
    _initialized: bool = False

    @classmethod
    def register_page(cls, page: BulutPage) -> None:
        """Register a new page. Raises ValueError if ID exists."""
        if page.id in cls._pages:
            raise ValueError(f"Page ID '{page.id}' is already registered!")
        
        cls._pages[page.id] = page

    @classmethod
    def list_pages(cls, category: Optional[str] = None) -> List[BulutPage]:
        """List registered pages, optionally filtered by category, ordered by 'order'."""
        items = list(cls._pages.values())
        if category:
            items = [p for p in items if p.category_tr == category]
            
        return sorted(items, key=lambda p: p.order)

    @classmethod
    def get_page(cls, page_id: str) -> BulutPage:
        """Get page by ID."""
        if page_id not in cls._pages:
            raise KeyError(f"Page ID '{page_id}' not found in registry.")
        return cls._pages[page_id]

    @classmethod
    def get_categories(cls) -> List[str]:
        """Get unique categories in defined order preference."""
        # Predefined sort order for known categories
        known_order = ["Operasyon", "Risk", "Performans", "Ticaret", "Adli İnceleme", "Intel", "Geliştirici"]
        
        cats = set(p.category_tr for p in cls._pages.values())
        
        # Sort: Known ones first in order, then others alphabetically
        sorted_cats = [c for c in known_order if c in cats]
        others = sorted([c for c in cats if c not in known_order])
        
        return sorted_cats + others

    @classmethod
    def reset(cls):
        """Reset registry (for testing)."""
        cls._pages = {}
        cls._initialized = False
