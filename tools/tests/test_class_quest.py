from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.class_quest_catalog import (
    ALLIANCE_FACTION_MASK,
    HORDE_FACTION_MASK,
    SUMMON_IMP_SPELL_ID,
)
from aracgen.emit_class_quest import ClassQuestEmitter, ClassQuestResult, compute_class_quests
from aracgen.geography import quest_access_tier
from aracgen.matrix import ComboMatrix, class_bit, race_bit
from aracgen.snapshot import load_snapshot
from aracgen.stock_loader import StockKitStore

SQL_ROOT = Path(__file__).resolve().parents[2] / "data" / "sql"
SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshot"


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
    horde = {qid for qid, p in shaman.items() if p.new_allowable_races == HORDE_FACTION_MASK}
    assert horde == {1516, 1517, 1518, 1519, 1520, 1521}
    assert shaman[1516].new_allowable_races == HORDE_FACTION_MASK
    assert shaman[1519].new_allowable_races == HORDE_FACTION_MASK


def test_faction_unlock_shaman_alliance_water_air_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    shaman = _faction_patches_for_class(result, 7)
    alliance = {qid for qid, p in shaman.items() if p.new_allowable_races == ALLIANCE_FACTION_MASK}
    # Call of Water (20) + Call of Air (30) exist only as the Draenei chain on
    # the Alliance side; stock Call of Fire (10) is already faction-wide (1101).
    assert alliance == {
        9500, 9501, 9503, 9504, 9508, 9509, 10490,  # Call of Water
        9547, 9551, 9552, 9553, 9554, 10491,  # Call of Air
    }
    # Each widens stock Draenei-only (1024) to the full Alliance mask.
    assert all(shaman[qid].original_allowable_races == 1024 for qid in alliance)
    assert all(shaman[qid].new_allowable_races == ALLIANCE_FACTION_MASK for qid in alliance)


def test_faction_unlock_druid_bear_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    druid = _faction_patches_for_class(result, 11)
    bear = {5921, 5922, 5929, 5930, 5931, 5932, 6001, 6002}
    assert bear <= set(druid)
    assert druid[5921].new_allowable_races == ALLIANCE_FACTION_MASK
    assert druid[5922].new_allowable_races == HORDE_FACTION_MASK


def test_faction_unlock_druid_aquatic_form_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    druid = _faction_patches_for_class(result, 11)
    # Aquatic Form (spell 1446) mirrors bear form: NE (8) / Tauren (32) only.
    alliance = {5923, 5924, 5925, 26, 29, 272, 5061}
    horde = {5926, 5927, 5928, 27, 28, 30, 31}
    for qid in alliance:
        assert druid[qid].new_allowable_races == ALLIANCE_FACTION_MASK
    for qid in horde:
        assert druid[qid].new_allowable_races == HORDE_FACTION_MASK
    assert druid[5061].original_allowable_races == 8  # NE Aquatic Form
    assert druid[31].original_allowable_races == 32  # Tauren Aquatic Form
    # Bear (8) + Aquatic (14) = 22 druid faction patches total.
    assert len(druid) == 22


def test_faction_unlock_paladin_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    paladin = _faction_patches_for_class(result, 2)
    # 23 original Redemption entries + 39 from the full DB-verified audit.
    assert len(paladin) == 62
    assert paladin[1642].new_allowable_races == ALLIANCE_FACTION_MASK
    assert paladin[9676].new_allowable_races == HORDE_FACTION_MASK


def test_faction_unlock_paladin_full_audit_chains() -> None:
    result = compute_class_quests(ComboMatrix.stock(), StockKitStore.load())
    paladin = _faction_patches_for_class(result, 2)

    # Redemption roots/variants + Draenei "Jol" root (Alliance -> 1101).
    redemption_alliance = {3101, 1641, 1790, 2998, 3681, 3107, 1645, 1789,
                           2997, 2999, 3000, 10366}
    # Level-60 Charger epic mount chain, stock mask 1029 (Hu+Dw+Dr).
    charger_alliance = {7637, 7638, 7639, 7640, 7641, 7642, 7643, 7644,
                        7645, 7646, 7647, 7670}
    # Blood Knight trials/weapon + warhorse + charger (BE -> 690).
    blood_knight_horde = {10069, 9681, 9686, 9690, 9691, 9692, 9707, 9710,
                          9712, 9721, 9722, 9723, 9735, 9736, 9737}

    for qid in redemption_alliance | charger_alliance:
        assert paladin[qid].new_allowable_races == ALLIANCE_FACTION_MASK
    for qid in blood_knight_horde:
        assert paladin[qid].new_allowable_races == HORDE_FACTION_MASK

    assert paladin[10366].original_allowable_races == 1024  # Draenei "Jol" root
    assert paladin[7637].original_allowable_races == 1029  # Charger (Hu+Dw+Dr)

    # 9287 ("Paladin Training", Draenei) is hard-blocked behind a Draenei-only
    # non-class prereq (9280); unlocking it would be futile, so it is excluded.
    assert 9287 not in paladin


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


@pytest.fixture(scope="session")
def baked_snapshot():
    try:
        return load_snapshot(snapshot_dir=SNAPSHOT_DIR)
    except FileNotFoundError:
        pytest.skip("baked world snapshot not present")


@pytest.mark.parametrize(
    "table",
    ["quest_template", "quest_template_addon", "playercreateinfo_spell_custom"],
)
def test_install_sql_matches_checked_in_artifact(baked_snapshot, table: str) -> None:
    install_path = SQL_ROOT / "db-world" / f"mod_uac_{table}.sql"
    if not install_path.is_file():
        pytest.skip(f"Checked-in SQL not found: {install_path}")
    emitter = ClassQuestEmitter(
        ComboMatrix.stock(),
        StockKitStore.load(),
        snapshot=baked_snapshot,
    )
    generated = emitter.render_install_files()[table]
    assert generated == install_path.read_text(encoding="utf-8")
