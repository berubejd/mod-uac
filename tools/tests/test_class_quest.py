from __future__ import annotations

from aracgen.class_quest_catalog import (
    ALLIANCE_FACTION_MASK,
    HORDE_FACTION_MASK,
    SUMMON_IMP_SPELL_ID,
)
from aracgen.emit_class_quest import ClassQuestEmitter, ClassQuestResult, compute_class_quests
from aracgen.geography import quest_access_tier
from aracgen.matrix import ComboMatrix, class_bit, race_bit
from aracgen.stock_loader import StockKitStore


def _faction_patches_for_class(result: ClassQuestResult, class_id: int):
    return {
        p.quest_id: p
        for p in result.quest_patches
        if p.tier == "faction" and p.class_id == class_id
    }


def test_tier_classification_cross_continent_is_c() -> None:
    assert quest_access_tier(141, 1) == "C"  # Teldrassil -> Dun Morogh
    assert quest_access_tier(1, 1) == "A"
    assert quest_access_tier(12, 1) == "B"  # Elwynn -> Dun Morogh (both EK)


def test_dwarf_warlock_patches_gnome_imp_quests() -> None:
    matrix = ComboMatrix.stock()
    store = StockKitStore.load()
    result = compute_class_quests(matrix, store)

    dwarf_patches = [p for p in result.quest_patches if p.race_id == 3 and p.class_id == 9]
    quest_ids = {patch.quest_id for patch in dwarf_patches}
    assert quest_ids == {1599, 3115}
    assert all(patch.tier == "A" for patch in dwarf_patches)
    assert {patch.new_allowable_races for patch in dwarf_patches} == {68}  # 64 | 4
    assert not any(row.race_id == 3 for row in result.spell_grants)


def test_night_elf_warlock_grants_imp_at_creation() -> None:
    matrix = ComboMatrix.stock()
    store = StockKitStore.load()
    result = compute_class_quests(matrix, store)

    ne_grants = [row for row in result.spell_grants if row.race_id == 4 and row.class_id == 9]
    assert len(ne_grants) == 1
    assert ne_grants[0].spell_id == SUMMON_IMP_SPELL_ID
    assert ne_grants[0].tier == "C"
    assert not any(row.race_id == 4 for row in result.quest_patches)


def test_tauren_warlock_needs_no_quest_or_spell_patch() -> None:
    matrix = ComboMatrix.stock()
    store = StockKitStore.load()
    result = compute_class_quests(matrix, store)

    assert not any(row.race_id == 6 and row.class_id == 9 for row in result.quest_patches)
    assert not any(row.race_id == 6 and row.class_id == 9 for row in result.spell_grants)


def test_faction_unlock_warrior_ironforge_chain() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    warrior = _faction_patches_for_class(result, 1)
    assert set(warrior) == {1678, 1679}
    assert warrior[1678].original_allowable_races == 68
    assert warrior[1678].new_allowable_races == ALLIANCE_FACTION_MASK


def test_faction_unlock_shaman_horde_earth_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    shaman = _faction_patches_for_class(result, 7)
    assert set(shaman) == {1516, 1517, 1518, 1519, 1520, 1521}
    assert shaman[1516].new_allowable_races == HORDE_FACTION_MASK
    assert shaman[1519].new_allowable_races == HORDE_FACTION_MASK


def test_faction_unlock_druid_bear_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    druid = _faction_patches_for_class(result, 11)
    assert set(druid) == {5921, 5922, 5929, 5930, 5931, 5932, 6001, 6002}
    assert druid[5921].new_allowable_races == ALLIANCE_FACTION_MASK
    assert druid[5922].new_allowable_races == HORDE_FACTION_MASK


def test_faction_unlock_paladin_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    paladin = _faction_patches_for_class(result, 2)
    assert len(paladin) == 23
    assert paladin[1642].new_allowable_races == ALLIANCE_FACTION_MASK
    assert paladin[9676].new_allowable_races == HORDE_FACTION_MASK


def test_stock_ac_needs_no_addon_anti_gray_patches() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    assert result.addon_patches == ()


def test_uninstall_sql_restores_stock_masks_and_removes_spell_grants() -> None:
    matrix = ComboMatrix.stock()
    emitter = ClassQuestEmitter(matrix, StockKitStore.load())
    result = emitter.compute()
    quest_uninstall = emitter.render_uninstall_files(result)["quest_template"]
    spell_uninstall = emitter.render_uninstall_files(result)["playercreateinfo_spell_custom"]

    assert "SET `AllowableRaces` = 64 WHERE `ID` = 1599" in quest_uninstall
    assert "SET `AllowableRaces` = 68 WHERE `ID` = 1678" in quest_uninstall
    assert "SET `AllowableRaces` = 512 WHERE `ID` = 9676" in quest_uninstall
    assert (
        f"DELETE FROM `playercreateinfo_spell_custom` "
        f"WHERE `racemask` = {race_bit(4)} AND `classmask` = {class_bit(9)} "
        f"AND `Spell` = {SUMMON_IMP_SPELL_ID}"
    ) in spell_uninstall
