from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.emit_player import PlayerCreateEmitter, build_resolver
from aracgen.item_prototypes import DEFAULT_ITEM_PROTOTYPES_PATH
from aracgen.kits import CanonicalKitResolver
from aracgen.snapshot import load_snapshot
from aracgen.sources import ZipDbcSource
from aracgen.stock_loader import StockKitStore, spawn_for_race

DATA_ZIP = Path(__file__).resolve().parents[2] / "data" / "cache" / "client-data-v19.zip"
STOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "stock" / "db_world"
ITEM_PROTOTYPES = DEFAULT_ITEM_PROTOTYPES_PATH
SQL_ROOT = Path(__file__).resolve().parents[2] / "data" / "sql"
SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshot"


@pytest.fixture(scope="session")
def resolver() -> CanonicalKitResolver:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    if not ITEM_PROTOTYPES.is_file():
        pytest.skip(f"Item prototypes not found: {ITEM_PROTOTYPES}")
    source = ZipDbcSource(DATA_ZIP)
    return build_resolver(
        source.load_char_start_outfit(),
        stock_dir=STOCK_DIR,
        item_prototypes_path=ITEM_PROTOTYPES,
    )


def test_spawn_for_race_uses_tauren_starting_zone() -> None:
    store = StockKitStore.load(STOCK_DIR)
    spawn = spawn_for_race(store, 6)
    assert spawn.zone_id == 215


def test_reference_race_is_faction_matched(resolver: CanonicalKitResolver) -> None:
    # Tauren mage -> lowest horde race with mage is undead (5).
    assert resolver.reference_race_for_class(8, 6) == 5
    # Human druid -> alliance druid reference is night elf (4).
    assert resolver.reference_race_for_class(11, 1) == 4


def test_tauren_mage_has_racial_war_stomp(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(6, 8)
    action_spells = {entry.action for entry in kit.actions}
    assert 133 in action_spells  # Fireball from mage kit
    assert 20549 in action_spells  # War Stomp


def test_tauren_mage_outfit_from_horde_mage_reference(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(6, 8)
    item_ids = {
        item_id
        for record in kit.outfit_records
        for item_id in record.positive_item_ids()
    }
    assert 1395 in item_ids  # mage staff from horde reference outfit
    assert 6948 in item_ids  # hearthstone


def test_dwarf_mage_skips_outfit_when_char_start_outfit_exists(
    resolver: CanonicalKitResolver,
) -> None:
    kit = resolver.resolve(3, 8)
    assert kit.outfit_records == ()


def test_dwarf_mage_charstartoutfit_sql_omits_guarded_combo(
    resolver: CanonicalKitResolver,
) -> None:
    emitter = PlayerCreateEmitter(resolver)
    install = emitter.render_install_files()["charstartoutfit_dbc"]
    uninstall = emitter.render_uninstall_files()["charstartoutfit_dbc"]
    assert "-- (3, 8," not in install
    assert ", 3, 8," not in install.split("REPLACE INTO", 1)[-1]
    assert "(3, 8" not in uninstall
    assert "-- (6, 8," in install


def test_player_create_emitter_produces_38_combos(resolver: CanonicalKitResolver) -> None:
    result = PlayerCreateEmitter(resolver).compute()
    assert len(result.kits) == 38


def test_install_sql_includes_expected_tables(resolver: CanonicalKitResolver) -> None:
    emitter = PlayerCreateEmitter(resolver)
    result = emitter.compute()
    install = emitter.render_install_files(result)
    assert "INSERT INTO `playercreateinfo`" in install["playercreateinfo"]
    assert "INSERT INTO `playercreateinfo_action`" in install["playercreateinfo_action"]
    assert "REPLACE INTO `charstartoutfit_dbc`" in install["charstartoutfit_dbc"]
    assert "INSERT INTO `playercreateinfo_skills`" in install["playercreateinfo_skills"]
    assert "(6, 8," in install["playercreateinfo"]


def test_human_hunter_excludes_dk_class_spells(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(1, 3)
    action_spells = {entry.action for entry in kit.actions}
    assert 45477 not in action_spells
    assert 45462 not in action_spells
    assert 75 in action_spells  # hunter ability from reference kit
    assert 59752 in action_spells  # human Every Man for Himself


def test_human_shaman_uses_human_racial_not_draenei(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(1, 7)
    by_button = {entry.button: entry.action for entry in kit.actions}
    assert by_button[3] == 59752
    assert 59547 not in by_button.values()
    assert 9 not in by_button


def test_dwarf_shaman_uses_stoneform_not_find_minerals(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(3, 7)
    by_button = {entry.button: entry.action for entry in kit.actions}
    assert by_button[3] == 20594
    assert 2481 not in by_button.values()


def test_orc_mage_gets_spell_power_blood_fury(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(2, 8)
    by_button = {entry.button: entry.action for entry in kit.actions}
    assert by_button[2] == 33702
    assert 20572 not in by_button.values()
    assert 33697 not in by_button.values()


def test_gnome_shaman_uses_gnome_racial(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(7, 7)
    by_button = {entry.button: entry.action for entry in kit.actions}
    assert by_button[3] == 20589
    assert 59547 not in by_button.values()


def test_undead_shaman_uses_undead_racial(resolver: CanonicalKitResolver) -> None:
    kit = resolver.resolve(5, 7)
    by_button = {entry.button: entry.action for entry in kit.actions}
    assert by_button[3] == 20577
    assert 33697 not in by_button.values()


def test_uninstall_sql_targets_exact_combos(resolver: CanonicalKitResolver) -> None:
    emitter = PlayerCreateEmitter(resolver)
    result = emitter.compute()
    uninstall = emitter.render_uninstall_files(result)
    assert "DELETE FROM `playercreateinfo` WHERE (`race`, `class`) IN" in uninstall[
        "playercreateinfo"
    ]
    assert "(6, 8)" in uninstall["playercreateinfo_action"]


@pytest.fixture
def fresh_resolver() -> CanonicalKitResolver:
    if not DATA_ZIP.is_file():
        pytest.skip(f"Canonical data not found: {DATA_ZIP}")
    if not ITEM_PROTOTYPES.is_file():
        pytest.skip(f"Item prototypes not found: {ITEM_PROTOTYPES}")
    source = ZipDbcSource(DATA_ZIP)
    return build_resolver(
        source.load_char_start_outfit(),
        stock_dir=STOCK_DIR,
        item_prototypes_path=ITEM_PROTOTYPES,
    )


@pytest.fixture(scope="session")
def baked_snapshot():
    try:
        return load_snapshot(snapshot_dir=SNAPSHOT_DIR)
    except FileNotFoundError:
        pytest.skip("baked world snapshot not present")


@pytest.mark.parametrize(
    "table",
    [
        "playercreateinfo",
        "playercreateinfo_action",
        "charstartoutfit_dbc",
        "playercreateinfo_skills",
    ],
)
def test_install_sql_matches_checked_in_artifact(
    fresh_resolver: CanonicalKitResolver,
    baked_snapshot,
    table: str,
) -> None:
    install_path = SQL_ROOT / "db-world" / f"mod_uac_{table}.sql"
    if not install_path.is_file():
        pytest.skip(f"Checked-in SQL not found: {install_path}")
    emitter = PlayerCreateEmitter(fresh_resolver, snapshot=baked_snapshot)
    generated = emitter.render_install_files()[table]
    assert generated == install_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "table",
    [
        "playercreateinfo",
        "playercreateinfo_action",
        "charstartoutfit_dbc",
        "playercreateinfo_skills",
    ],
)
def test_uninstall_sql_matches_checked_in_artifact(
    fresh_resolver: CanonicalKitResolver,
    table: str,
) -> None:
    uninstall_path = SQL_ROOT / "db-uninstall" / f"mod_uac_{table}_uninstall.sql"
    if not uninstall_path.is_file():
        pytest.skip(f"Checked-in SQL not found: {uninstall_path}")
    emitter = PlayerCreateEmitter(fresh_resolver)
    generated = emitter.render_uninstall_files()[table]
    assert generated == uninstall_path.read_text(encoding="utf-8")
