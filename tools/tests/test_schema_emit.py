from __future__ import annotations

import pytest

from aracgen.schema_emit import (
    format_sql_literal,
    normalize_int_for_column,
    prepare_row,
    render_insert,
    render_replace,
    resolve_logical_column,
)
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import ColumnDef, TableSchema


@pytest.fixture(scope="session")
def skill_schema():
    return load_snapshot().schema("skillraceclassinfo_dbc")


def test_prepare_row_fills_schema_defaults(skill_schema) -> None:
    row = prepare_row(skill_schema, {"ID": 971, "SkillID": 43, "RaceMask": 512})
    assert row["ID"] == 971
    assert row["SkillID"] == 43
    assert row["RaceMask"] == 512
    assert row["ClassMask"] == 0
    assert row["SkillTierID"] == 0


def test_prepare_row_rejects_unknown_logical_field(skill_schema) -> None:
    with pytest.raises(ValueError, match="Unknown logical field"):
        prepare_row(skill_schema, {"NotAColumn": 1})


def test_creature_entry_alias_resolves_id1() -> None:
    schema = TableSchema(
        table="creature",
        columns=(
            ColumnDef("guid", 1, "int unsigned", False, None),
            ColumnDef("id1", 2, "int unsigned", False, "0"),
        ),
    )
    assert resolve_logical_column(schema, "entry") == "id1"
    row = prepare_row(schema, {"entry": 895})
    assert row["id1"] == 895
    assert row["guid"] is None


def test_render_insert_matches_skill_overlay_shape(skill_schema) -> None:
    sql = render_insert(
        "skillraceclassinfo_dbc",
        skill_schema,
        {
            "ID": 971,
            "SkillID": 43,
            "RaceMask": 512,
            "ClassMask": 1,
            "Flags": 128,
            "MinLevel": 0,
            "SkillTierID": 0,
            "SkillCostIndex": 0,
        },
    )
    assert (
        sql
        == "INSERT INTO `skillraceclassinfo_dbc` "
        "(`ID`, `SkillID`, `RaceMask`, `ClassMask`, `Flags`, `MinLevel`, "
        "`SkillTierID`, `SkillCostIndex`) VALUES "
        "(971, 43, 512, 1, 128, 0, 0, 0);"
    )


def test_format_sql_literal_null_and_string() -> None:
    assert format_sql_literal(None) == "NULL"
    assert format_sql_literal("it's") == "'it''s'"


def test_normalize_int_for_column_signed_wrap() -> None:
    column = ColumnDef("ItemID_1", 6, "int", False, "0")
    assert normalize_int_for_column(0x80000001, column) == -2147483647


def test_render_replace_prefixes_insert() -> None:
    schema = TableSchema(
        table="charstartoutfit_dbc",
        columns=(
            ColumnDef("ID", 1, "int", False, None),
            ColumnDef("RaceID", 2, "tinyint unsigned", False, "0"),
        ),
    )
    sql = render_replace(
        "charstartoutfit_dbc",
        schema,
        {"ID": 971, "RaceID": 1},
    )
    assert sql.startswith("REPLACE INTO `charstartoutfit_dbc`")
    assert "971, 1" in sql
