"""
Tezaver Core - Molds (Archetypes)
=================================

Defines the standard set of 6+1 Archetypes (Kalıplar) used throughout the pipeline.
"""

from enum import Enum
from typing import Dict, List

class Archetype(str, Enum):
    GRIND = "GRIND"
    GUILLOTINE = "GUILLOTINE"
    SUPERNOVA = "SUPERNOVA"
    PHOENIX = "PHOENIX"
    SURFER = "SURFER"
    CRASH = "CRASH"

# User-Facing Labels with Emojis
ARCHETYPE_LABELS: Dict[Archetype, str] = {
    Archetype.GRIND: "GRIND 🪜",
    Archetype.GUILLOTINE: "GUILLOTINE 🩸",
    Archetype.SUPERNOVA: "SUPERNOVA 💥",
    Archetype.PHOENIX: "PHOENIX 🔥",
    Archetype.SURFER: "SURFER 🏄‍♂️",
    Archetype.CRASH: "CRASH ⚠️"
}

ARCHETYPE_DESCRIPTIONS: Dict[Archetype, str] = {
    Archetype.GRIND: "Düşük hacimli, sinsi yükseliş (yatay kırılım veya mevcut trend devamı).",
    Archetype.GUILLOTINE: "Sert düşüş sonrası ani V-dönüşü / Ayı tuzağı.",
    Archetype.SUPERNOVA: "Ani ve devasa hacim patlaması ile dikey yükseliş.",
    Archetype.PHOENIX: "Önceki zirveden düşüş sonrası küllerinden doğuş (Rebound).",
    Archetype.SURFER: "Hareketli ortalama üzerinde (MA50/EMA) trend sörfü.",
    Archetype.CRASH: "Piyasa çöküşü sonrası reflex toparlanma (Yüksek risk)."
}

def get_all_archetypes() -> List[Archetype]:
    return list(Archetype)
