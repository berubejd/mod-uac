"""Constants and class metadata for the starter trainer emitter."""

from __future__ import annotations

import re
from dataclasses import dataclass

from aracgen.snapshot_model import MOD_UAC_CREATURE_GUID_MIN

TRAINER_GUID_BASE = MOD_UAC_CREATURE_GUID_MIN
CURATED_SPELL_THRESHOLD = 30
PLACEMENT_GAP = 2.0
PLACEMENT_STEP = 2.0
TRAINER_SPAWN_TIME_SECS = 180

CLASS_TRAINER_RE = re.compile(
    r"(Warrior|Paladin|Hunter|Rogue|Priest|Shaman|Mage|Warlock|Druid) Trainer"
)

CLASS_NAME_TO_ID: dict[str, int] = {
    "Warrior": 1,
    "Paladin": 2,
    "Hunter": 3,
    "Rogue": 4,
    "Priest": 5,
    "Shaman": 7,
    "Mage": 8,
    "Warlock": 9,
    "Druid": 11,
}

CLASS_ORDER: tuple[str, ...] = tuple(CLASS_NAME_TO_ID)

ID_TO_CLASS_NAME: dict[int, str] = {
    class_id: name for name, class_id in CLASS_NAME_TO_ID.items()
}

# Spec §3.3 — highest-priority kin with a native trainer present in-zone.
CLASS_KINSHIP: dict[str, tuple[str, ...]] = {
    "Warrior": ("Paladin", "Rogue", "Hunter"),
    "Paladin": ("Warrior", "Priest", "Rogue"),
    "Hunter": ("Rogue", "Warrior", "Paladin"),
    "Rogue": ("Hunter", "Warrior", "Paladin"),
    "Priest": ("Shaman", "Druid", "Mage", "Paladin"),
    "Shaman": ("Druid", "Priest", "Paladin"),
    "Druid": ("Shaman", "Priest", "Hunter"),
    "Mage": ("Warlock", "Priest"),
    "Warlock": ("Mage", "Priest"),
}

# Human-readable labels keyed by (map_id, zone_id) from stock playercreateinfo anchors.
STARTER_ZONE_LABELS: dict[tuple[int, int], str] = {
    (0, 1): "Coldridge",
    (0, 12): "Northshire",
    (0, 85): "Deathknell",
    (1, 14): "ValleyOfTrials",
    (1, 141): "Shadowglen",
    (1, 215): "CampNarache",
    (530, 3431): "Sunstrider",
    (530, 3526): "AmmenVale",
}

# Stable emission order (matches legacy hand SQL / prototype zone list).
ZONE_PROCESS_ORDER: tuple[str, ...] = (
    "Northshire",
    "Coldridge",
    "Shadowglen",
    "AmmenVale",
    "ValleyOfTrials",
    "CampNarache",
    "Deathknell",
    "Sunstrider",
)


@dataclass(frozen=True, slots=True)
class TrainerOverride:
    zone: str
    class_name: str
    entry: int | None = None
    anchor: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    o: float | None = None


def trainer_class_name(name: str, subname: str) -> str | None:
    match = CLASS_TRAINER_RE.search(f"{name} {subname}")
    return match.group(1) if match else None


def zone_label(map_id: int, zone_id: int) -> str:
    return STARTER_ZONE_LABELS.get((map_id, zone_id), f"map{map_id}_zone{zone_id}")
