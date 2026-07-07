"""Item class/subclass → skill mapping aligned with ItemTemplate::GetSkill()."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ITEM_PROTOTYPES_PATH = REPO_ROOT / "data" / "item_prototypes.json"

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


def items_payload_to_prototypes(items: Mapping[str | int, Any]) -> dict[int, ItemPrototype]:
    prototypes: dict[int, ItemPrototype] = {}
    for raw_id, raw_values in items.items():
        item_id = int(raw_id)
        if not isinstance(raw_values, (list, tuple)) or len(raw_values) != 2:
            msg = f"Invalid item prototype entry for {item_id!r}: {raw_values!r}"
            raise ValueError(msg)
        item_class, sub_class = (int(value) for value in raw_values)
        prototypes[item_id] = ItemPrototype(item_id, item_class, sub_class)
    return prototypes


def load_item_prototypes_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Invalid item prototypes file (expected object): {path}"
        raise ValueError(msg)
    return payload


def write_item_prototypes_file(
    path: Path,
    items: Mapping[int, tuple[int, int]],
    *,
    source: str | None = None,
    version: str | None = None,
) -> Path:
    payload = {
        "captured_at": datetime.now(UTC).isoformat(),
        "source": source,
        "version": version,
        "items": {
            str(item_id): [item_class, sub_class]
            for item_id, (item_class, sub_class) in sorted(items.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def extract_item_prototypes_from_ac_sql(
    sql_path: Path,
    item_ids: frozenset[int],
) -> dict[int, tuple[int, int]]:
    """Bootstrap helper: scan AC base item_template.sql for requested entries only."""
    if not item_ids:
        return {}
    wanted = set(item_ids)
    found: dict[int, tuple[int, int]] = {}
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        match = _ITEM_ROW.match(line.strip())
        if match is None:
            continue
        item_id, item_class, sub_class = (int(value) for value in match.groups())
        if item_id not in wanted:
            continue
        found[item_id] = (item_class, sub_class)
        if len(found) == len(wanted):
            break
    missing = wanted - found.keys()
    if missing:
        msg = f"item_template.sql missing entries: {sorted(missing)}"
        raise ValueError(msg)
    return found


class ItemPrototypeStore:
    def __init__(self, path: Path | None = None) -> None:
        target = path or DEFAULT_ITEM_PROTOTYPES_PATH
        if not target.is_file():
            msg = (
                f"Item prototypes not found: {target}. "
                "Run generate_* with --refresh-snapshot or ensure data/item_prototypes.json "
                "is present."
            )
            raise FileNotFoundError(msg)
        payload = load_item_prototypes_payload(target)
        items = payload.get("items")
        if not isinstance(items, dict):
            msg = f"Invalid item prototypes file (missing items map): {target}"
            raise ValueError(msg)
        self._prototypes = items_payload_to_prototypes(items)
        self._path = target

    @classmethod
    def from_items(cls, items: Mapping[int, tuple[int, int]]) -> ItemPrototypeStore:
        store = cls.__new__(cls)
        store._prototypes = {
            item_id: ItemPrototype(item_id, item_class, sub_class)
            for item_id, (item_class, sub_class) in items.items()
        }
        store._path = None
        return store

    def get(self, item_id: int) -> ItemPrototype:
        try:
            return self._prototypes[item_id]
        except KeyError as exc:
            msg = f"Item {item_id} not found in item prototype source"
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
