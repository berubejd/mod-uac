"""Item class/subclass → skill mapping aligned with ItemTemplate::GetSkill()."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AC_ITEM_TEMPLATE = (
    REPO_ROOT.parent
    / "azerothcore-wotlk"
    / "data"
    / "sql"
    / "base"
    / "db_world"
    / "item_template.sql"
)

ITEM_CLASS_WEAPON = 2
ITEM_CLASS_ARMOR = 4

# SharedDefines.h / ItemTemplate.h — weapon subclass index → skill id.
_WEAPON_SKILLS: tuple[int, ...] = (
    44,  # Axe
    172,  # Axe2H
    45,  # Bow
    46,  # Gun
    54,  # Mace
    160,  # Mace2H
    229,  # Polearm
    43,  # Sword
    55,  # Sword2H
    0,
    136,  # Staff
    0,
    0,
    473,  # Fist
    0,
    173,  # Dagger
    176,  # Thrown
    0,
    226,  # Crossbow
    0,
    0,
)

# Armor subclass index → skill id (cloth … shield).
_ARMOR_SKILLS: tuple[int, ...] = (
    0,
    415,  # Cloth
    414,  # Leather
    413,  # Mail
    293,  # Plate
    0,
    433,  # Shield
    0,
    0,
    0,
    0,
)

# Hunter ranged weapon skills granted via race-masked playercreateinfo_skills rows.
RANGED_WEAPON_SKILLS: frozenset[int] = frozenset({45, 46, 226})

# playercreateinfo_skills Thrown row (classMask 9 covers hunter among others).
THROWN_SKILL = 176

# Weapon skill → item weapon subclass indices (ItemTemplate.h).
SKILL_WEAPON_SUBCLASSES: dict[int, frozenset[int]] = {
    45: frozenset({2}),  # Bow
    46: frozenset({3}),  # Gun
    226: frozenset({18}),  # Crossbow
    176: frozenset({16}),  # Thrown
}


@dataclass(frozen=True, slots=True)
class ItemPrototype:
    item_id: int
    item_class: int
    sub_class: int

    def required_skill(self) -> int:
        if self.item_class == ITEM_CLASS_WEAPON:
            if self.sub_class >= len(_WEAPON_SKILLS):
                return 0
            return _WEAPON_SKILLS[self.sub_class]
        if self.item_class == ITEM_CLASS_ARMOR:
            if self.sub_class >= len(_ARMOR_SKILLS):
                return 0
            return _ARMOR_SKILLS[self.sub_class]
        return 0


_ITEM_ROW = re.compile(r"^\((\d+),(\d+),(\d+),")


@lru_cache(maxsize=1)
def _load_all_prototypes(path: Path) -> dict[int, ItemPrototype]:
    text = path.read_text(encoding="utf-8", errors="replace")
    prototypes: dict[int, ItemPrototype] = {}
    for line in text.splitlines():
        match = _ITEM_ROW.match(line.strip())
        if match is None:
            continue
        item_id, item_class, sub_class = (int(value) for value in match.groups())
        prototypes[item_id] = ItemPrototype(item_id, item_class, sub_class)
    return prototypes


class ItemPrototypeStore:
    def __init__(self, sql_path: Path | None = None) -> None:
        path = sql_path or AC_ITEM_TEMPLATE
        if not path.is_file():
            msg = f"item_template.sql not found: {path}"
            raise FileNotFoundError(msg)
        self._prototypes = _load_all_prototypes(path)

    def get(self, item_id: int) -> ItemPrototype:
        try:
            return self._prototypes[item_id]
        except KeyError as exc:
            msg = f"Item {item_id} not found in item template source"
            raise KeyError(msg) from exc

    def skills_for_items(self, item_ids: set[int]) -> frozenset[int]:
        skills: set[int] = set()
        for item_id in item_ids:
            skill_id = self.get(item_id).required_skill()
            if skill_id:
                skills.add(skill_id)
        return frozenset(skills)

    def weapon_subclasses_for_items(self, item_ids: set[int]) -> frozenset[int]:
        subclasses: set[int] = set()
        for item_id in item_ids:
            proto = self.get(item_id)
            if proto.item_class == ITEM_CLASS_WEAPON:
                subclasses.add(proto.sub_class)
        return frozenset(subclasses)
