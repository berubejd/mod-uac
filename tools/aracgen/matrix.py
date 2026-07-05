"""Playable race/class combo matrix derived from stock AzerothCore."""

from __future__ import annotations

from dataclasses import dataclass

# Playable in WotLK 3.3.5a (Goblin=9 and class 10 omitted).
PLAYABLE_RACES: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 10, 11})
PLAYABLE_CLASSES: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 11})

# Stock `playercreateinfo` rows from AzerothCore base db_world (62 combos).
STOCK_EXISTING_COMBOS: frozenset[tuple[int, int]] = frozenset(
    {
        (1, 1),
        (1, 2),
        (1, 4),
        (1, 5),
        (1, 6),
        (1, 8),
        (1, 9),
        (2, 1),
        (2, 3),
        (2, 4),
        (2, 6),
        (2, 7),
        (2, 9),
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
        (3, 5),
        (3, 6),
        (4, 1),
        (4, 3),
        (4, 4),
        (4, 5),
        (4, 6),
        (4, 11),
        (5, 1),
        (5, 4),
        (5, 5),
        (5, 6),
        (5, 8),
        (5, 9),
        (6, 1),
        (6, 3),
        (6, 6),
        (6, 7),
        (6, 11),
        (7, 1),
        (7, 4),
        (7, 6),
        (7, 8),
        (7, 9),
        (8, 1),
        (8, 3),
        (8, 4),
        (8, 5),
        (8, 6),
        (8, 7),
        (8, 8),
        (10, 2),
        (10, 3),
        (10, 4),
        (10, 5),
        (10, 6),
        (10, 8),
        (10, 9),
        (11, 1),
        (11, 2),
        (11, 3),
        (11, 5),
        (11, 6),
        (11, 7),
        (11, 8),
    }
)


def race_bit(race_id: int) -> int:
    return 1 << (race_id - 1)


def class_bit(class_id: int) -> int:
    return 1 << (class_id - 1)


def mask_covers_race_class(race_mask: int, class_mask: int, race_id: int, class_id: int) -> bool:
    """Mirror AzerothCore GetSkillRaceClassInfo mask checks (DBCStores.cpp)."""
    if race_mask and not (race_mask & race_bit(race_id)):
        return False
    return not class_mask or bool(class_mask & class_bit(class_id))


@dataclass(frozen=True, slots=True)
class ComboMatrix:
    """Target playable matrix minus stock combos; DK rows are never added."""

    existing: frozenset[tuple[int, int]]
    new_combos: frozenset[tuple[int, int]]

    @classmethod
    def stock(cls) -> ComboMatrix:
        target = {
            (race, class_id)
            for race in PLAYABLE_RACES
            for class_id in PLAYABLE_CLASSES
            if class_id != 6  # DK already all-race in stock playercreateinfo
        }
        existing = STOCK_EXISTING_COMBOS
        return cls(existing=existing, new_combos=frozenset(target - existing))

    def is_new(self, race_id: int, class_id: int) -> bool:
        return (race_id, class_id) in self.new_combos
