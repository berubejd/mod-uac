"""Compute playercreateinfo_skills overlays for new race/class combos."""

from __future__ import annotations

from dataclasses import dataclass

from aracgen.item_prototypes import (
    RANGED_WEAPON_SKILLS,
    SKILL_WEAPON_SUBCLASSES,
    THROWN_SKILL,
    ItemPrototypeStore,
)
from aracgen.matrix import class_bit, mask_covers_race_class, race_bit
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
    item_ids: frozenset[int],
    store: StockKitStore,
    item_prototypes: ItemPrototypeStore,
    *,
    ref_race: int,
) -> tuple[StarterSkillRow, ...]:
    """Gear-derived skills plus reference weapon-skill sanity check."""
    weapon_subclasses = item_prototypes.weapon_subclasses_for_items(set(item_ids))

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


def starter_skill_row_to_create_info(row: StarterSkillRow) -> CreateInfoSkill:
    return CreateInfoSkill(
        race_mask=race_bit(row.race_id),
        class_mask=class_bit(row.class_id),
        skill_id=row.skill_id,
        rank=row.rank,
    )


def load_playercreateinfo_skills_catalog(
    source_outfit,
    *,
    resolver=None,
) -> tuple[CreateInfoSkill, ...]:
    """Stock plus mod-uac gear-skill rows — the full server starting-skill grant set."""
    from aracgen.emit_player import build_resolver, compute_player_create

    kit_resolver = resolver or build_resolver(source_outfit)
    mod_skills = tuple(
        starter_skill_row_to_create_info(row)
        for kit in compute_player_create(kit_resolver).kits
        for row in kit.skills
    )
    return kit_resolver.store.create_skills + mod_skills
