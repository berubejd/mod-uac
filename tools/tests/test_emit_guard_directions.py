"""Tests for capital guard POI / gossip emission (Phase 2d)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aracgen.emit_guard_directions import (
    GuardDirectionsEmitter,
    compute_guard_directions,
    render_install,
    render_uninstall,
)
from aracgen.emit_trainers import compute_capital_trainer_result, load_trainer_overrides
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import (
    MOD_UAC_GUARD_MENU_MIN,
    MOD_UAC_GUARD_NPC_TEXT_MIN,
    MOD_UAC_GUARD_POI_MIN,
    Snapshot,
    load_table_schema_from_ac_base,
)

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES_PATH = ROOT / "data" / "trainer_overrides.yaml"
AC_BASE = ROOT.parent / "azerothcore-wotlk" / "data" / "sql" / "base" / "db_world"
CHECKED_IN_INSTALL = ROOT / "data" / "sql" / "db-world" / "mod_uac_capital_guard_poi.sql"
CHECKED_IN_UNINSTALL = (
    ROOT / "data" / "sql" / "db-uninstall" / "mod_uac_capital_guard_poi_uninstall.sql"
)

# Stock AC capital class submenu wiring (from world DB capture).
CAPITAL_CLASS_MENUS = [
    {
        "capital": "Ironforge",
        "class_menu_ids": [2144],
        "menus": [
            {
                "menu_id": 2144,
                "max_option_id": 7,
                "present_classes": [
                    "Hunter",
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Rogue",
                    "Shaman",
                    "Warlock",
                    "Warrior",
                ],
            }
        ],
    },
    {
        "capital": "Darnassus",
        "class_menu_ids": [2343],
        "menus": [
            {
                "menu_id": 2343,
                "max_option_id": 6,
                "present_classes": [
                    "Druid",
                    "Hunter",
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Rogue",
                    "Warrior",
                ],
            }
        ],
    },
    {
        "capital": "Exodar",
        "class_menu_ids": [7787],
        "menus": [
            {
                "menu_id": 7787,
                "max_option_id": 6,
                "present_classes": [
                    "Druid",
                    "Hunter",
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Shaman",
                    "Warrior",
                ],
            }
        ],
    },
    {
        "capital": "Orgrimmar",
        "class_menu_ids": [1949],
        "menus": [
            {
                "menu_id": 1949,
                "max_option_id": 7,
                "present_classes": [
                    "Hunter",
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Rogue",
                    "Shaman",
                    "Warlock",
                    "Warrior",
                ],
            }
        ],
    },
    {
        "capital": "Undercity",
        "class_menu_ids": [2848, 10768],
        "menus": [
            {
                "menu_id": 2848,
                "max_option_id": 5,
                "present_classes": [
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Rogue",
                    "Warlock",
                    "Warrior",
                ],
            },
            {
                "menu_id": 10768,
                "max_option_id": 5,
                "present_classes": [
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Rogue",
                    "Warlock",
                    "Warrior",
                ],
            },
        ],
    },
    {
        "capital": "ThunderBluff",
        "class_menu_ids": [740],
        "menus": [
            {
                "menu_id": 740,
                "max_option_id": 5,
                "present_classes": [
                    "Druid",
                    "Hunter",
                    "Mage",
                    "Priest",
                    "Shaman",
                    "Warrior",
                ],
            }
        ],
    },
    {
        "capital": "Silvermoon",
        "class_menu_ids": [7649],
        "menus": [
            {
                "menu_id": 7649,
                "max_option_id": 6,
                "present_classes": [
                    "Druid",
                    "Hunter",
                    "Mage",
                    "Paladin",
                    "Priest",
                    "Rogue",
                    "Warlock",
                ],
            }
        ],
    },
]


@pytest.fixture(scope="session")
def baked_snapshot() -> Snapshot:
    return load_snapshot()


@pytest.fixture(scope="session")
def guard_snapshot(baked_snapshot: Snapshot) -> Snapshot:
    if not AC_BASE.is_dir():
        pytest.skip(f"AC base schemas not found at {AC_BASE}")
    payload = copy.deepcopy(baked_snapshot.to_json())
    trainers = payload.setdefault("data", {}).setdefault("trainers", {})
    trainers["capital_class_menus"] = CAPITAL_CLASS_MENUS
    schemas = payload.setdefault("schemas", {})
    for table in ("points_of_interest", "npc_text", "gossip_menu", "gossip_menu_option"):
        if table not in schemas:
            schemas[table] = load_table_schema_from_ac_base(AC_BASE, table).to_json()
    return Snapshot.from_json(payload)


@pytest.fixture(scope="session")
def guard_result(guard_snapshot: Snapshot) -> object:
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    capital = compute_capital_trainer_result(guard_snapshot, overrides=overrides)
    return compute_guard_directions(guard_snapshot, capital.rows)


def test_guard_emits_one_poi_per_capital_trainer(guard_result) -> None:
    assert len(guard_result.artifacts) == 14
    assert len(guard_result.poi_ids) == 14
    assert guard_result.poi_ids[0] == MOD_UAC_GUARD_POI_MIN


def test_undercity_duplicate_menus_share_one_poi(guard_result) -> None:
    undercity_hunter = [
        option
        for option in guard_result.options
        if option.class_name == "Hunter" and option.class_menu_id in {2848, 10768}
    ]
    assert len(undercity_hunter) == 2
    assert undercity_hunter[0].poi_id == undercity_hunter[1].poi_id


def test_poi_coordinates_match_capital_trainers(guard_snapshot: Snapshot, guard_result) -> None:
    overrides = load_trainer_overrides(OVERRIDES_PATH)
    capital = compute_capital_trainer_result(guard_snapshot, overrides=overrides)
    by_key = {(row.zone_label, row.class_name): row for row in capital.rows}
    for artifact in guard_result.artifacts:
        row = by_key[(artifact.capital, artifact.class_name)]
        assert artifact.trainer_x == row.x
        assert artifact.trainer_y == row.y


def test_generated_confirm_text_uses_trainer_entry_name(
    guard_snapshot: Snapshot, guard_result
) -> None:
    sql = render_install(guard_result, snapshot=guard_snapshot)
    assert "marked the location on your map" in sql
    assert "Mathrengyl Bearwalker, the Druid trainer" in sql
    assert "with the other class trainers in Ironforge" in sql


def test_install_sql_matches_checked_in_artifact(guard_snapshot: Snapshot, guard_result) -> None:
    if not CHECKED_IN_INSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_INSTALL}")
    generated = render_install(guard_result, snapshot=guard_snapshot)
    assert generated == CHECKED_IN_INSTALL.read_text(encoding="utf-8")


def test_uninstall_sql_matches_checked_in_artifact(guard_result) -> None:
    if not CHECKED_IN_UNINSTALL.is_file():
        pytest.skip(f"Checked-in SQL not found: {CHECKED_IN_UNINSTALL}")
    generated = render_uninstall(guard_result)
    assert generated == CHECKED_IN_UNINSTALL.read_text(encoding="utf-8")


def test_emitter_end_to_end(guard_snapshot: Snapshot) -> None:
    emitter = GuardDirectionsEmitter(
        snapshot=guard_snapshot,
        overrides=load_trainer_overrides(OVERRIDES_PATH),
    )
    result = emitter.compute()
    install = emitter.render_install(result)
    assert "DELETE FROM `points_of_interest`" in install
    assert str(MOD_UAC_GUARD_NPC_TEXT_MIN) in install
    assert str(MOD_UAC_GUARD_MENU_MIN) in install
    assert len(result.options) == 17
