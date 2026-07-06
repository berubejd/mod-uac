"""Compute playercreateinfo_skills overlays for new race/class combos."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.item_prototypes import (
    RANGED_WEAPON_SKILLS,
    THROWN_SKILL,
    ItemPrototypeStore,
    SKILL_WEAPON_SUBCLASSES,
)
from aracgen.matrix import mask_covers_race_class
from aracgen.stock_loader import CreateInfoSkill, StockKitStore


@dataclass(frozen=True, slots=True)
class StarterSkillRow:
    race_id: int
    class_id: int
    skill_id: int
    rank: int = 0


def _stock_skills_for_combo(
    rows: tuple[CreateInfoSkill, ...],
    race_id: int,
    class_id: int,
) -> frozenset[int]:
    return frozenset(
        row.skill_id
        for row in rows
        if mask_covers_race_class(row.race_mask, row.class_mask, race_id, class_id)
    )


def _reference_weapon_fallback(
    store: StockKitStore,
    *,
    race_id: int,
    class_id: int,
    ref_race: int,
    weapon_subclasses: frozenset[int],
) -> frozenset[int]:
    ref_skills = _stock_skills_for_combo(store.create_skills, ref_race, class_id)
    new_skills = _stock_skills_for_combo(store.create_skills, race_id, class_id)
    candidates = (ref_skills - new_skills) & (RANGED_WEAPON_SKILLS | {THROWN_SKILL})
    fallback: set[int] = set()
    for skill_id in candidates:
        subclasses = SKILL_WEAPON_SUBCLASSES.get(skill_id)
        if subclasses is None:
            continue
        if subclasses & weapon_subclasses:
            fallback.add(skill_id)
    return frozenset(fallback)


def compute_starter_skills(
    race_id: int,
    class_id: int,
    items: tuple[tuple[int, int], ...],
    store: StockKitStore,
    item_prototypes: ItemPrototypeStore,
    *,
    ref_race: int,
) -> tuple[StarterSkillRow, ...]:
    """Gear-derived skills plus reference weapon-skill sanity check."""
    item_ids = {item_id for item_id, _amount in items}
    weapon_subclasses = item_prototypes.weapon_subclasses_for_items(item_ids)

    gear_skills = item_prototypes.skills_for_items(item_ids)
    ref_fallback = _reference_weapon_fallback(
        store,
        race_id=race_id,
        class_id=class_id,
        ref_race=ref_race,
        weapon_subclasses=weapon_subclasses,
    )
    stock_skills = _stock_skills_for_combo(store.create_skills, race_id, class_id)
    needed = (gear_skills | ref_fallback) - stock_skills

    return tuple(
        StarterSkillRow(race_id=race_id, class_id=class_id, skill_id=skill_id)
        for skill_id in sorted(needed)
    )
