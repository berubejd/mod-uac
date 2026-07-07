from __future__ import annotations

from pathlib import Path

import pytest

from aracgen.schema_emit import format_sql_literal, normalize_int_for_column
from aracgen.snapshot import load_snapshot
from aracgen.snapshot_model import ColumnDef
from aracgen.sources import cached_client_data_zip
from aracgen.spell_dbc_export import export_spell_row, find_spell_record, load_spell_table


def test_normalize_int_for_column_maps_dbc_sentinels() -> None:
    signed = ColumnDef(
        name="ReagentCount_6",
        ordinal=1,
        type="int",
        nullable=False,
        default=0,
    )
    unsigned = ColumnDef(
        name="Attributes",
        ordinal=2,
        type="int unsigned",
        nullable=False,
        default=0,
    )
    assert normalize_int_for_column(0xFFFFFFFF, signed) == -1
    assert normalize_int_for_column(0x80000000, signed) == -2147483648
    assert normalize_int_for_column(42, signed) == 42
    assert normalize_int_for_column(0xFFFFFFFF, unsigned) == 0xFFFFFFFF


def test_format_sql_literal_renders_signed_ints() -> None:
    assert format_sql_literal(-1) == "-1"
    assert format_sql_literal(4294967295) == "4294967295"


def test_export_spell_row_uses_signed_reagent_counts() -> None:
    cache = Path(__file__).resolve().parents[2] / "data" / "cache"
    zip_path = cached_client_data_zip(cache)
    if not zip_path.exists():
        pytest.skip("canonical client-data cache not present")

    snapshot = load_snapshot()
    table = load_spell_table(zip_path)
    row = export_spell_row(table, 1515, snapshot=snapshot)
    assert "4294967295" not in row
    assert ", -1," in row or ", -1)" in row


def test_record_values_aligns_base_level_with_schema() -> None:
    cache = Path(__file__).resolve().parents[2] / "data" / "cache"
    zip_path = cached_client_data_zip(cache)
    if not zip_path.exists():
        pytest.skip("canonical client-data cache not present")

    snapshot = load_snapshot()
    schema = snapshot.schema("spell_dbc")
    table = load_spell_table(zip_path)
    record_index = find_spell_record(table, 1515)
    table.set_uint32(record_index, 38, 1)
    table.set_uint32(record_index, 39, 1)
    row = export_spell_row(table, 1515, snapshot=snapshot)
    values_part = row.split("VALUES (", maxsplit=1)[1].rsplit(");", maxsplit=1)[0]
    prefix = values_part.split("'Tame Beast'", maxsplit=1)[0]
    parts = [part.strip() for part in prefix.split(",")]
    columns = schema.column_names()
    assert parts[columns.index("BaseLevel")] == "1"
    assert parts[columns.index("SpellLevel")] == "1"
    assert "4294967295" not in row
