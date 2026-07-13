"""Constants for capital guard POI / gossip emission (Phase 2d)."""

from __future__ import annotations

from aracgen.trainer_catalog import CLASS_NAME_TO_ID

CLASS_TRAINER_ROOT_TEXTS: tuple[str, ...] = (
    "Class Trainer",
    "A class trainer",
    "Class trainer",
)

PLAYABLE_CLASS_NAMES: frozenset[str] = frozenset(CLASS_NAME_TO_ID)

# Stock gossip_menu_option.OptionBroadcastTextID per class label (from AC world DB).
CLASS_OPTION_BROADCAST_TEXT: dict[str, int] = {
    "Druid": 45409,
    "Hunter": 50546,
    "Paladin": 48028,
    "Rogue": 45406,
    "Shaman": 45410,
    "Warlock": 45407,
    "Warrior": 45408,
    "Mage": 45404,
}

POI_ICON = 7
POI_FLAGS = 99


def poi_name(capital_label: str, class_name: str) -> str:
    return f"{capital_label} {class_name} Trainer"


def confirm_text(capital_display: str, class_name: str, entry_name: str) -> str:
    return (
        f"You'll find {entry_name}, the {class_name} trainer, with the other "
        f"class trainers in {capital_display}. I've marked the location on your map."
    )
