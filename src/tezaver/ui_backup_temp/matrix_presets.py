# Matrix Presets
"""
Preset profiles for Matrix UI.
Defines CANLI, SAVAŞ, SNIPER presets with defaults.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# === Help Texts (Turkish) ===
HELP_TEXTS = {
    "profil": "Matrix davranış profili. CANLI=Gerçek işlem, SAVAŞ=Backtest, SNIPER=Keskin giriş.",
    "guvenlik_seviyesi": "Güvenlik modu. Gözlem=Sadece izle, Sim=Simülasyon, Testnet=Test ağı, Gerçek=Canlı.",
    "allowlist": "İzin verilen semboller listesi. Sadece bu semboller işleme alınır.",
    "timeframe": "Zaman dilimleri. Örn: 15m, 1h, 4h.",
    "on_kontrol": "İşlem öncesi temel kontroller (bakiye, margin, limit).",
    "kart_kapisi": "Strateji kartı onay durumu kontrolü.",
    "risk_freni": "Risk limitleri ve max pozisyon kontrolü.",
    "reconcile": "İç durum ile borsa durumu eşleşme kontrolü.",
    "islem_tekrari": "Geçmiş işlemleri grafik üzerinde tekrarla ve analiz et.",
    "olay_gezgini": "Sistem olaylarını filtrele ve incele.",
    "paketler": "Hata/uyarı durumlarında oluşturulan olay paketleri.",
    "cozumlenmis_ayarlar": "Profil + override sonrası nihai ayarlar.",
}

# === Safety Levels ===
SAFETY_LEVELS = ["GÖZLEM", "SIM", "TESTNET", "GERÇEK"]

# === Default Allowlists ===
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
DEFAULT_TIMEFRAMES = ["15m", "1h"]


@dataclass
class MatrixPreset:
    """Matrix UI preset configuration."""
    
    name: str  # CANLI, SAVAŞ, SNIPER
    label_tr: str  # Turkish label
    description: str  # Short description
    
    # Defaults
    safety_level: str = "SIM"
    allowlist: List[str] = field(default_factory=lambda: DEFAULT_SYMBOLS.copy())
    timeframes: List[str] = field(default_factory=lambda: DEFAULT_TIMEFRAMES.copy())
    telemetry_verbosity: str = "NORMAL"  # QUIET, NORMAL, VERBOSE
    
    # Behavior flags
    is_live: bool = False
    is_backtest: bool = False
    is_sniper: bool = False
    
    # UI defaults
    auto_start: bool = False
    show_trade_replay: bool = True
    show_diagnostics: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# === Preset Definitions ===
PRESET_CANLI = MatrixPreset(
    name="CANLI",
    label_tr="🟢 Canlı İşlem",
    description="Gerçek borsa bağlantısı ile canlı işlem modu.",
    safety_level="TESTNET",
    is_live=True,
    telemetry_verbosity="VERBOSE",
    auto_start=False,
)

PRESET_SAVAS = MatrixPreset(
    name="SAVAŞ",
    label_tr="⚔️ Savaş Oyunu",
    description="Geçmiş veri üzerinde backtest simülasyonu.",
    safety_level="SIM",
    is_backtest=True,
    telemetry_verbosity="NORMAL",
    show_diagnostics=True,
)

PRESET_SNIPER = MatrixPreset(
    name="SNIPER",
    label_tr="🎯 Sniper Arena",
    description="Keskin giriş noktaları için özel test modu.",
    safety_level="SIM",
    is_sniper=True,
    timeframes=["15m"],
    telemetry_verbosity="QUIET",
)

ALL_PRESETS: Dict[str, MatrixPreset] = {
    "CANLI": PRESET_CANLI,
    "SAVAŞ": PRESET_SAVAS,
    "SNIPER": PRESET_SNIPER,
}


def get_preset(name: str) -> MatrixPreset:
    """Get preset by name. Defaults to CANLI if not found."""
    return ALL_PRESETS.get(name, PRESET_CANLI)


def resolve_preset(preset_name: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Resolve final settings from preset + overrides.
    
    Args:
        preset_name: CANLI, SAVAŞ, or SNIPER
        overrides: Optional dict of overrides
        
    Returns:
        Resolved settings dict
    """
    preset = get_preset(preset_name)
    resolved = preset.to_dict()
    
    if overrides:
        for key, value in overrides.items():
            if key in resolved and value is not None:
                resolved[key] = value
    
    return resolved


def preset_help_text(topic: str) -> str:
    """
    Get Turkish help text for a topic.
    
    Args:
        topic: Help topic key
        
    Returns:
        Turkish help text (1-2 sentences)
    """
    return HELP_TEXTS.get(topic.lower(), "Bilgi mevcut değil.")


def get_preset_names() -> List[str]:
    """Get list of all preset names."""
    return list(ALL_PRESETS.keys())


def get_preset_labels() -> Dict[str, str]:
    """Get preset name -> Turkish label mapping."""
    return {name: p.label_tr for name, p in ALL_PRESETS.items()}
