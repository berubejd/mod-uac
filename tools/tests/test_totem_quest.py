from __future__ import annotations

import copy
from pathlib import Path

import pytest
from aracgen.emit_totem_quest import (
    TotemQuestEmitter,
    compute_totem_quests,
    resolve_shaman_trainer_entry,
)
from aracgen.emit_trainers import compute_trainer_rows
from aracgen.matrix import ComboMatrix
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import MOD_UAC_QUEST_ID_MIN
from aracgen.totem_quest_catalog import (
    EARTH_ACCESS_QUESTS,
    EARTH_CHAIN_RENARROW,
    EARTH_TOTEM_ITEM_ID,
)

SQL_ROOT = Path(__file__).resolve().parents[2] / "data" / "sql"
ALL_PLAYABLE_RACES_MASK = 1791  # ten 3.3.5 races (excludes Goblin 256)


@pytest.fixture(scope="module")
def snapshot():
    return load_snapshot()


@pytest.fixture(scope="module")
def trainer_rows(snapshot):
    return compute_trainer_rows(snapshot, ComboMatrix.stock()).rows


def test_derives_expected_shaman_trainers(trainer_rows, snapshot):
    assert resolve_shaman_trainer_entry("alliance", trainer_rows, snapshot) == 17089
    assert resolve_shaman_trainer_entry("horde", trainer_rows, snapshot) == 3062


def test_deterministic_reserved_quest_ids(trainer_rows, snapshot):
    result = compute_totem_quests(trainer_rows, snapshot)
    assert result.quest_ids["alliance"] == MOD_UAC_QUEST_ID_MIN
    assert result.quest_ids["horde"] == MOD_UAC_QUEST_ID_MIN + 1
    assert result.trainer_entries == {"alliance": 17089, "horde": 3062}


def test_questgiver_validation_rejects_non_questgiver(trainer_rows, snapshot):
    # Strip the QUESTGIVER bit (2) from the Alliance shaman trainer template.
    mutated = copy.deepcopy(snapshot)
    mutated.data["trainers"]["creature_template"]["17089"]["npcflag"] = 51 & ~2
    with pytest.raises(ValueError, match="not a QUESTGIVER"):
        resolve_shaman_trainer_entry("alliance", trainer_rows, mutated)


def test_earth_totem_paths_partition_all_races() -> None:
    # Every race reachable by exactly one Earth Totem path: masks disjoint, union 1791.
    synthetic = [quest.allowable_races for quest in EARTH_ACCESS_QUESTS]  # 77, 528
    vanilla = {
        native for _qid, _stock, native in EARTH_CHAIN_RENARROW
    }  # {130, 32, 1024}
    masks = [*synthetic, *vanilla]

    union = 0
    total = 0
    for mask in masks:
        assert union & mask == 0, f"race overlap in mask {mask}"
        union |= mask
        total += mask
    assert union == ALL_PLAYABLE_RACES_MASK
    assert total == ALL_PLAYABLE_RACES_MASK


def test_install_rewards_earth_totem_and_renarrows(snapshot, trainer_rows):
    emitter = TotemQuestEmitter(snapshot=snapshot)
    result = compute_totem_quests(trainer_rows, snapshot)
    install = emitter.render_install(result)

    assert "`RewardItem1`" in install
    assert str(EARTH_TOTEM_ITEM_ID) in install
    assert (
        "INSERT INTO `creature_queststarter` (`id`, `quest`) VALUES (17089, 6000000)"
        in install
    )
    assert (
        "INSERT INTO `creature_questender` (`id`, `quest`) VALUES (3062, 6000001)"
        in install
    )
    for quest_id in (9449, 9450, 9451):
        assert f"SET `AllowableRaces` = 1024 WHERE `ID` = {quest_id}" in install


def test_uninstall_restores_stock_and_clears_band(snapshot):
    emitter = TotemQuestEmitter(snapshot=snapshot)
    uninstall = emitter.render_uninstall()
    assert (
        "DELETE FROM `quest_template` WHERE `ID` BETWEEN 6000000 AND 6009999"
        in uninstall
    )
    # 9449-9451 are Draenei-only (1024) in stock AC, so uninstall restores 1024.
    for quest_id in (9449, 9450, 9451):
        assert f"SET `AllowableRaces` = 1024 WHERE `ID` = {quest_id}" in uninstall


def test_install_sql_matches_checked_in_artifact(snapshot) -> None:
    install_path = SQL_ROOT / "db-world" / "mod_uac_shaman_totem_quests.sql"
    if not install_path.is_file():
        pytest.skip(f"Checked-in SQL not found: {install_path}")
    emitter = TotemQuestEmitter(snapshot=snapshot)
    assert emitter.render_install() == install_path.read_text(encoding="utf-8")
