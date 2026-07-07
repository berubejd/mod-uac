from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.emit_totem import (
    ALLIANCE_TOTEM_REFERENCE_RACE,
    HORDE_TOTEM_REFERENCE_RACE,
    REFERENCE_TOTEM_MODELS,
    TotemEmitter,
    off_race_shaman_races,
)
from aracgen.matrix import ComboMatrix
from aracgen.snapshot import load_snapshot

SQL_ROOT = Path(__file__).resolve().parents[2] / "data" / "sql"
SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshot"


def test_off_race_shaman_races_excludes_stock_totem_races() -> None:
    matrix = ComboMatrix.stock()
    assert off_race_shaman_races(matrix) == (1, 4, 5, 7, 10)


def test_alliance_races_use_dwarf_totem_models() -> None:
    matrix = ComboMatrix.stock()
    result = TotemEmitter(matrix).compute()
    dwarf_models = REFERENCE_TOTEM_MODELS[ALLIANCE_TOTEM_REFERENCE_RACE]
    for race_id in (1, 4, 7):
        race_rows = [row for row in result.rows if row.race_id == race_id]
        assert len(race_rows) == 4
        assert {row.model_id for row in race_rows} == set(dwarf_models.values())


def test_horde_races_use_orc_totem_models() -> None:
    matrix = ComboMatrix.stock()
    result = TotemEmitter(matrix).compute()
    orc_models = REFERENCE_TOTEM_MODELS[HORDE_TOTEM_REFERENCE_RACE]
    for race_id in (5, 10):
        race_rows = [row for row in result.rows if row.race_id == race_id]
        assert len(race_rows) == 4
        assert {row.model_id for row in race_rows} == set(orc_models.values())


def test_dwarf_shaman_does_not_emit_totem_rows() -> None:
    matrix = ComboMatrix.stock()
    result = TotemEmitter(matrix).compute()
    assert 3 not in {row.race_id for row in result.rows}


def test_install_sql_is_idempotent_and_uninstall_targets_races() -> None:
    matrix = ComboMatrix.stock()
    emitter = TotemEmitter(matrix)
    result = emitter.compute()
    install = emitter.render_install(result)
    uninstall = emitter.render_uninstall(result)

    assert "DELETE FROM `player_totem_model` WHERE `RaceID` IN (1, 4, 5, 7, 10)" in install
    assert "INSERT INTO `player_totem_model`" in install
    assert "(1, 1, 30754)" in install
    assert "(1, 5, 30758)" in install
    assert uninstall.count("DELETE FROM `player_totem_model`") == 1
    assert "(1, 4, 5, 7, 10)" in uninstall


@pytest.fixture(scope="session")
def baked_snapshot():
    try:
        return load_snapshot(snapshot_dir=SNAPSHOT_DIR)
    except FileNotFoundError:
        pytest.skip("baked world snapshot not present")


def test_install_sql_matches_checked_in_artifact(baked_snapshot) -> None:
    install_path = SQL_ROOT / "db-world" / "mod_uac_player_totem_model.sql"
    if not install_path.is_file():
        pytest.skip(f"Checked-in SQL not found: {install_path}")
    emitter = TotemEmitter(ComboMatrix.stock(), snapshot=baked_snapshot)
    generated = emitter.render_install(emitter.compute())
    assert generated == install_path.read_text(encoding="utf-8")


def test_uninstall_sql_matches_checked_in_artifact() -> None:
    uninstall_path = SQL_ROOT / "db-uninstall" / "mod_uac_player_totem_model_uninstall.sql"
    if not uninstall_path.is_file():
        pytest.skip(f"Checked-in SQL not found: {uninstall_path}")
    emitter = TotemEmitter(ComboMatrix.stock())
    generated = emitter.render_uninstall(emitter.compute())
    assert generated == uninstall_path.read_text(encoding="utf-8")
