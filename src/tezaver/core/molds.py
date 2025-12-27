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
    NINJA = "NINJA"
    SURFER = "SURFER"
    OTHER = "OTHER"

# User-Facing Labels with Emojis
ARCHETYPE_LABELS: Dict[Archetype, str] = {
    Archetype.GRIND: "GRIND 🪜",
    Archetype.GUILLOTINE: "GUILLOTINE 🩸",
    Archetype.SUPERNOVA: "SUPERNOVA 💥",
    Archetype.PHOENIX: "PHOENIX 🔥",
    Archetype.NINJA: "NINJA 🥷",
    Archetype.SURFER: "SURFER 🏄‍♂️",
    Archetype.OTHER: "OTHER 👽"
}

ARCHETYPE_DESCRIPTIONS: Dict[Archetype, str] = {
    Archetype.GRIND: "Sinsi, düşük hacimli, istikrarlı merdiven çıkışı.",
    Archetype.GUILLOTINE: "Sert düşüş sonrası ani V-dönüşü / Ayı tuzağı.",
    Archetype.SUPERNOVA: "Ani ve devasa hacim patlaması ile dikey yükseliş.",
    Archetype.PHOENIX: "Önceki zirveden düşüş sonrası küllerinden doğuş (Rebound).",
    Archetype.NINJA: "Yatay piyasada hacimsiz kırılım ve sessiz ilerleyiş.",
    Archetype.SURFER: "Hareketli ortalama üzerinde (MA50/EMA) trend sörfü.",
    Archetype.OTHER: "Belirgin bir kalıba uymayan veya karmaşık yapılar."
}

def get_all_archetypes() -> List[Archetype]:
    return list(Archetype)
