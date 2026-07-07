from __future__ import annotations

import json
from pathlib import Path

import pytest

from aracgen.snapshot import (
    _exclude_gated_spawns,
    filter_trainer_extract,
    is_mod_uac_creature_guid,
    load_snapshot,
    resolve_baked_snapshot_path,
    scrub_mod_uac_trainer_spawns,
    slim_trainer_snapshot,
    write_latest_pointer,
)
from aracgen.snapshot_dsn import DatabaseDsn, read_config_file, resolve_world_database_info
from aracgen.snapshot_model import (
    ColumnDef,
    Snapshot,
    TableSchema,
    build_spawn_defaults,
    creature_entry_column,
    sanitize_db_version,
    snapshot_filename_version,
)
from aracgen.snapshot_zones import STARTER_SPAWN_BOX_RADIUS, spawn_in_starter_box
from aracgen.snapshot_zones import build_starter_zone_boxes as _build_boxes

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "world_snapshot_minimal.json"


def test_spawn_in_starter_box_includes_boundary() -> None:
    boxes = _build_boxes(
        [
            {
                "race": 1,
                "class": 1,
                "map": 0,
                "zone": 12,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "o": 0.0,
            }
        ]
    )
    assert spawn_in_starter_box(
        map_id=0,
        x=STARTER_SPAWN_BOX_RADIUS,
        y=0.0,
        boxes=boxes,
    )


def test_exclude_gated_spawns_removes_matching_guids() -> None:
    trainers = {
        "gated_guids": [100],
        "creature_spawns": [
            {"guid": 100, "entry": 1, "map": 0, "x": 0.0, "y": 0.0, "z": 0.0, "o": 0.0},
            {"guid": 200, "entry": 2, "map": 0, "x": 0.0, "y": 0.0, "z": 0.0, "o": 0.0},
        ],
    }
    filtered = _exclude_gated_spawns(trainers)
    assert "gated_guids" not in filtered
    assert [spawn["guid"] for spawn in filtered["creature_spawns"]] == [200]


def test_slim_trainer_snapshot_drops_gated_spawn_rows() -> None:
    playercreateinfo = [
        {
            "race": 1,
            "class": 1,
            "map": 0,
            "zone": 12,
            "x": -8949.95,
            "y": -132.493,
            "z": 83.5312,
            "o": 0.0,
        }
    ]
    bloated = Snapshot(
        version="test",
        version_raw="test",
        core_version=None,
        core_revision=None,
        captured_at="2026-01-01T00:00:00+00:00",
        source="test",
        schemas={},
        data={
            "trainers": {
                "playercreateinfo": playercreateinfo,
                "gated_guids": [999],
                "creature_default_trainer": {"895": 7, "198": 16},
                "trainer_spell_counts": {"7": 5, "16": 6},
                "trainers": {
                    "7": {"type": 0, "requirement": 3},
                    "16": {"type": 0, "requirement": 8},
                },
                "creature_template": {
                    "895": {"name": "Hunter", "subname": "Hunter Trainer", "faction": 55},
                    "198": {"name": "Mage", "subname": "Mage Trainer", "faction": 12},
                },
                "creature_spawns": [
                    {
                        "guid": 999,
                        "entry": 198,
                        "map": 0,
                        "x": -8850.0,
                        "y": -190.0,
                        "z": 89.0,
                        "o": 0.0,
                        "equipment_id": 1,
                        "curhealth": 1,
                        "curmana": 0,
                        "npcflag": 0,
                    },
                    {
                        "guid": 100,
                        "entry": 895,
                        "map": 0,
                        "x": -8850.0,
                        "y": -190.0,
                        "z": 89.0,
                        "o": 0.0,
                        "equipment_id": 1,
                        "curhealth": 102,
                        "curmana": 0,
                        "npcflag": 0,
                    },
                ],
                "spawn_defaults": {},
            }
        },
    )
    slim = slim_trainer_snapshot(bloated)
    assert "gated_guids" not in slim.data["trainers"]
    assert all(spawn["guid"] != 999 for spawn in slim.data["trainers"]["creature_spawns"])
    assert "198" not in slim.data["trainers"]["creature_default_trainer"]


def test_scrub_mod_uac_trainer_spawns_trims_orphan_metadata() -> None:
    snapshot = Snapshot(
        version="test",
        version_raw="test",
        core_version=None,
        core_revision=None,
        captured_at="2026-01-01T00:00:00+00:00",
        source="test",
        schemas={},
        data={
            "trainers": {
                "creature_spawns": [
                    {
                        "guid": 6_000_000,
                        "entry": 895,
                        "map": 0,
                        "x": 1.0,
                        "y": 2.0,
                        "z": 3.0,
                        "o": 4.0,
                        "equipment_id": 9,
                        "curhealth": 1,
                        "curmana": 0,
                        "npcflag": 0,
                    },
                    {
                        "guid": 100,
                        "entry": 198,
                        "map": 0,
                        "x": 1.0,
                        "y": 2.0,
                        "z": 3.0,
                        "o": 4.0,
                        "equipment_id": 1,
                        "curhealth": 102,
                        "curmana": 0,
                        "npcflag": 0,
                    },
                ],
                "creature_default_trainer": {"895": 7, "198": 16},
                "trainer_spell_counts": {"7": 5, "16": 6},
                "trainers": {
                    "7": {"type": 0, "requirement": 3},
                    "16": {"type": 0, "requirement": 8},
                },
                "creature_template": {
                    "895": {"name": "Hunter", "subname": "Hunter Trainer", "faction": 55},
                    "198": {"name": "Mage", "subname": "Mage Trainer", "faction": 12},
                },
                "spawn_defaults": {
                    "895": {"equipment_id": 9, "curhealth": 1, "curmana": 0, "npcflag": 0},
                    "198": {"equipment_id": 1, "curhealth": 102, "curmana": 0, "npcflag": 0},
                },
            }
        },
    )
    cleaned = scrub_mod_uac_trainer_spawns(snapshot)
    assert "895" not in cleaned.data["trainers"]["creature_default_trainer"]
    assert cleaned.data["trainers"]["creature_default_trainer"]["198"] == 16


@pytest.fixture
def minimal_snapshot() -> Snapshot:
    return Snapshot.load(FIXTURE)


def test_sanitize_db_version() -> None:
    assert sanitize_db_version("ACDB 335.17-dev") == "ACDB_335.17-dev"
    assert sanitize_db_version("  ACDB 335.17-dev  ") == "ACDB_335.17-dev"
    assert sanitize_db_version(None).startswith("unknown-")


def test_snapshot_filename_version_adds_hash_when_lossy() -> None:
    key = snapshot_filename_version("ACDB 335.17-dev")
    assert key.startswith("ACDB_335.17-dev-")
    assert len(key.split("-")[-1]) == 8
    assert snapshot_filename_version("ACDB_335.17-dev") == "ACDB_335.17-dev"


def test_is_mod_uac_creature_guid() -> None:
    assert is_mod_uac_creature_guid(6_000_000)
    assert is_mod_uac_creature_guid(6_009_999)
    assert not is_mod_uac_creature_guid(5_999_999)


def test_build_spawn_defaults_uses_lowest_guid() -> None:
    rows = [
        {
            "guid": 200,
            "entry": 895,
            "equipment_id": 2,
            "curhealth": 50,
            "curmana": 0,
            "npcflag": 16,
        },
        {
            "guid": 100,
            "entry": 895,
            "equipment_id": 1,
            "curhealth": 102,
            "curmana": 0,
            "npcflag": 0,
        },
    ]
    defaults = build_spawn_defaults(rows)
    assert defaults["895"]["equipment_id"] == 1
    assert defaults["895"]["curhealth"] == 102


def test_scrub_mod_uac_trainer_spawns_rebuilds_defaults() -> None:
    snapshot = Snapshot(
        version="test",
        version_raw="test",
        core_version=None,
        core_revision=None,
        captured_at="2026-01-01T00:00:00+00:00",
        source="test",
        schemas={},
        data={
            "trainers": {
                "creature_spawns": [
                    {
                        "guid": 6_000_000,
                        "entry": 895,
                        "map": 0,
                        "x": 1.0,
                        "y": 2.0,
                        "z": 3.0,
                        "o": 4.0,
                        "equipment_id": 9,
                        "curhealth": 1,
                        "curmana": 0,
                        "npcflag": 0,
                    },
                    {
                        "guid": 100,
                        "entry": 895,
                        "map": 0,
                        "x": 1.0,
                        "y": 2.0,
                        "z": 3.0,
                        "o": 4.0,
                        "equipment_id": 1,
                        "curhealth": 102,
                        "curmana": 0,
                        "npcflag": 0,
                    },
                ],
                "spawn_defaults": {
                    "895": {"equipment_id": 9, "curhealth": 1, "curmana": 0, "npcflag": 0},
                },
            }
        },
    )
    cleaned = scrub_mod_uac_trainer_spawns(snapshot)
    assert len(cleaned.data["trainers"]["creature_spawns"]) == 1
    assert cleaned.data["trainers"]["spawn_defaults"]["895"]["equipment_id"] == 1


def test_scrub_mod_uac_trainer_spawns_prunes_defaults_without_equipment() -> None:
    snapshot = Snapshot(
        version="test",
        version_raw="test",
        core_version=None,
        core_revision=None,
        captured_at="2026-01-01T00:00:00+00:00",
        source="test",
        schemas={},
        data={
            "trainers": {
                "creature_spawns": [
                    {
                        "guid": 6_000_000,
                        "entry": 895,
                        "map": 0,
                        "x": 1.0,
                        "y": 2.0,
                        "z": 3.0,
                        "o": 4.0,
                    },
                    {
                        "guid": 100,
                        "entry": 198,
                        "map": 0,
                        "x": 1.0,
                        "y": 2.0,
                        "z": 3.0,
                        "o": 4.0,
                    },
                ],
                "spawn_defaults": {
                    "895": {"equipment_id": 9, "curhealth": 1, "curmana": 0, "npcflag": 0},
                    "198": {"equipment_id": 1, "curhealth": 102, "curmana": 0, "npcflag": 0},
                },
            }
        },
    )
    cleaned = scrub_mod_uac_trainer_spawns(snapshot)
    assert "895" not in cleaned.data["trainers"]["spawn_defaults"]
    assert cleaned.data["trainers"]["spawn_defaults"]["198"]["equipment_id"] == 1


def test_parse_ac_dsn() -> None:
    dsn = DatabaseDsn.parse("127.0.0.1;3306;acore;secret;acore_world")
    assert dsn.host == "127.0.0.1"
    assert dsn.port == 3306
    assert dsn.user == "acore"
    assert dsn.password == "secret"
    assert dsn.database == "acore_world"
    assert dsn.redacted == "127.0.0.1;3306;acore;***;acore_world"


def test_parse_ac_dsn_rejects_wrong_part_count() -> None:
    with pytest.raises(ValueError, match="got 4 parts"):
        DatabaseDsn.parse("127.0.0.1;3306;acore;acore_world")


def test_read_config_file(tmp_path: Path) -> None:
    config = tmp_path / "snapshot.conf"
    config.write_text(
        '\n'.join(
            [
                "# comment",
                'WorldDatabaseInfo = "10.0.0.5;3306;acore;pass;acore_world"',
            ]
        ),
        encoding="utf-8",
    )
    values = read_config_file(config)
    assert values["WorldDatabaseInfo"] == "10.0.0.5;3306;acore;pass;acore_world"


def test_resolve_world_database_info_prefers_cli(tmp_path: Path) -> None:
    config = tmp_path / "snapshot.conf"
    config.write_text('WorldDatabaseInfo = "1.1.1.1;3306;a;b;c"', encoding="utf-8")
    dsn = resolve_world_database_info(
        config_path=config,
        cli_dsn="127.0.0.1;3306;acore;secret;acore_world",
    )
    assert dsn.host == "127.0.0.1"


def test_resolve_world_database_info_env_override(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "snapshot.conf"
    config.write_text('WorldDatabaseInfo = "1.1.1.1;3306;a;b;c"', encoding="utf-8")
    monkeypatch.setenv(
        "MOD_UAC_WORLD_DATABASE_INFO",
        "192.168.1.10;3306;acore;secret;acore_world",
    )
    dsn = resolve_world_database_info(config_path=config)
    assert dsn.host == "192.168.1.10"


def test_resolve_world_database_info_from_config(tmp_path: Path) -> None:
    config = tmp_path / "snapshot.conf"
    config.write_text(
        'WorldDatabaseInfo = "db.example;3306;acore;secret;acore_world"',
        encoding="utf-8",
    )
    dsn = resolve_world_database_info(config_path=config)
    assert dsn.database == "acore_world"


def test_creature_entry_column_resolves_id(minimal_snapshot: Snapshot) -> None:
    schema = minimal_snapshot.schema("creature")
    assert creature_entry_column(schema) == "id"


def test_creature_entry_column_resolves_id1() -> None:
    schema = TableSchema(
        table="creature",
        columns=(ColumnDef("id1", 1, "int unsigned", False, "0"),),
    )
    assert creature_entry_column(schema) == "id1"


def test_snapshot_roundtrip(minimal_snapshot: Snapshot, tmp_path: Path) -> None:
    path = tmp_path / "roundtrip.json"
    minimal_snapshot.write(path)
    loaded = Snapshot.load(path)
    assert loaded.version == minimal_snapshot.version
    assert loaded.data["trainers"]["creature_spawns"][0]["entry"] == 895
    assert loaded.schema("creature").column_names()[1] == "id"


def test_load_snapshot_from_fixture_path(minimal_snapshot: Snapshot) -> None:
    loaded = load_snapshot(FIXTURE)
    assert loaded.version_raw == minimal_snapshot.version_raw


def test_trainer_extract_shape(minimal_snapshot: Snapshot) -> None:
    trainers = minimal_snapshot.data["trainers"]
    assert trainers["creature_default_trainer"]["895"] == 7
    assert trainers["trainer_spell_counts"]["7"] == 5
    assert trainers["trainers"]["7"]["requirement"] == 3
    assert trainers["playercreateinfo"][0]["race"] == 1
    assert "gated_guids" not in trainers
    assert "starter_zones" in trainers


def test_write_and_resolve_latest_pointer(tmp_path: Path) -> None:
    versioned = tmp_path / "world.test.json"
    minimal_snapshot = Snapshot.load(FIXTURE)
    minimal_snapshot.write(versioned)
    write_latest_pointer(tmp_path, versioned.name)
    assert resolve_baked_snapshot_path(tmp_path) == versioned
    loaded = load_snapshot(snapshot_dir=tmp_path)
    assert loaded.version == minimal_snapshot.version


def test_filter_trainer_extract_keeps_starter_zone_spawns() -> None:
    playercreateinfo = [
        {
            "race": 1,
            "class": 1,
            "map": 0,
            "zone": 12,
            "x": -8949.95,
            "y": -132.493,
            "z": 83.5312,
            "o": 0.0,
        }
    ]
    trainer_data = {
        "playercreateinfo": playercreateinfo,
        "creature_default_trainer": {"895": 7, "99999": 1},
        "trainer_spell_counts": {"7": 5, "1": 50},
        "trainers": {"7": {"type": 0, "requirement": 3}},
        "creature_template": {
            "895": {"name": "Thorgas Grimson", "subname": "Hunter Trainer", "faction": 55},
            "99999": {"name": "Far Away", "subname": "Mage Trainer", "faction": 12},
        },
        "creature_spawns": [
            {
                "guid": 100,
                "entry": 895,
                "map": 0,
                "x": -8850.0,
                "y": -190.0,
                "z": 89.0,
                "o": 1.5,
                "equipment_id": 1,
                "curhealth": 102,
                "curmana": 0,
                "npcflag": 0,
            },
            {
                "guid": 200,
                "entry": 99999,
                "map": 0,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "o": 0.0,
                "equipment_id": 0,
                "curhealth": 1,
                "curmana": 0,
                "npcflag": 0,
            },
        ],
        "spawn_defaults": {},
    }
    filtered = filter_trainer_extract(trainer_data)
    assert len(filtered["creature_spawns"]) == 1
    assert filtered["creature_spawns"][0]["entry"] == 895
    assert "99999" not in filtered["creature_default_trainer"]
    assert len(filtered["starter_zones"]) == 1


def test_slim_trainer_snapshot_drops_gated_guids(minimal_snapshot: Snapshot) -> None:
    bloated = Snapshot(
        version=minimal_snapshot.version,
        version_raw=minimal_snapshot.version_raw,
        core_version=minimal_snapshot.core_version,
        core_revision=minimal_snapshot.core_revision,
        captured_at=minimal_snapshot.captured_at,
        source=minimal_snapshot.source,
        schemas=minimal_snapshot.schemas,
        data={
            "trainers": {
                **minimal_snapshot.data["trainers"],
                "gated_guids": [1, 2, 3],
            }
        },
    )
    slim = slim_trainer_snapshot(bloated)
    assert "gated_guids" not in slim.data["trainers"]


def test_snapshot_json_is_valid() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["version"] == "ACDB_335.17-dev"
    assert "schemas" in payload
