"""Collect CharStartOutfit item IDs referenced by mod-uac player create overlays."""

from __future__ import annotations

from aracgen.charstartoutfit_export import clone_reference_outfits, stock_outfit_covers
from aracgen.dbc import DbcTable
from aracgen.kits import ALLIANCE_RACES, HORDE_RACES
from aracgen.matrix import ComboMatrix


def reference_race_for_class(matrix: ComboMatrix, class_id: int, target_race: int) -> int:
    faction = ALLIANCE_RACES if target_race in ALLIANCE_RACES else HORDE_RACES
    candidates = sorted(
        race
        for race, combo_class in matrix.existing
        if combo_class == class_id and race in faction
    )
    if not candidates:
        faction_name = "alliance" if target_race in ALLIANCE_RACES else "horde"
        msg = f"No stock reference for class {class_id} in faction {faction_name}"
        raise ValueError(msg)
    return candidates[0]


def collect_mod_uac_outfit_item_ids(
    outfit: DbcTable,
    matrix: ComboMatrix | None = None,
) -> frozenset[int]:
    """Item IDs from reference outfits cloned for new race/class combos."""
    combo_matrix = matrix or ComboMatrix.stock()
    item_ids: set[int] = set()
    for race_id, class_id in combo_matrix.new_combos:
        if stock_outfit_covers(outfit, race_id, class_id):
            continue
        ref_race = reference_race_for_class(combo_matrix, class_id, race_id)
        records, _next_id = clone_reference_outfits(
            outfit,
            race_id=race_id,
            class_id=class_id,
            ref_race=ref_race,
            next_record_id=1,
        )
        for record in records:
            item_ids.update(record.positive_item_ids())
    return frozenset(item_ids)
