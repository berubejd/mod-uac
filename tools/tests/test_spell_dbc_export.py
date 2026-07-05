from __future__ import annotations

import pytest

from aracgen.spell_dbc_export import (
    _load_spell_schema,
    _render_row_literals,
    _sql_literal,
    _to_signed_int32,
)


def test_to_signed_int32_maps_dbc_sentinels() -> None:
    assert _to_signed_int32(0xFFFFFFFF) == -1
    assert _to_signed_int32(0x80000000) == -2147483648
    assert _to_signed_int32(42) == 42


def test_sql_literal_respects_signed_columns() -> None:
    assert _sql_literal(0xFFFFFFFF, signed=True) == "-1"
    assert _sql_literal(0xFFFFFFFF, signed=False) == "4294967295"


def test_render_row_literals_emits_signed_reagent_counts() -> None:
    schema = _load_spell_schema()
    values: list[int | float | str | None] = [0 if column.signed else 0 for column in schema]
    reagent_count_6 = next(
        index for index, column in enumerate(schema) if column.name == "ReagentCount_6"
    )
    values[reagent_count_6] = 0xFFFFFFFF
    rendered = _render_row_literals(values)
    assert "4294967295" not in rendered
    assert ", -1," in rendered or rendered.endswith(", -1)")


def test_record_values_aligns_base_level_with_schema() -> None:
    from pathlib import Path

    from aracgen.sources import cached_client_data_zip

    cache = Path(__file__).resolve().parents[2] / "data" / "cache"
    zip_path = cached_client_data_zip(cache)
    if not zip_path.exists():
        pytest.skip("canonical client-data cache not present")

    from aracgen.spell_dbc_export import (
        _load_spell_columns,
        export_spell_row,
        find_spell_record,
        load_spell_table,
    )

    table = load_spell_table(zip_path)
    record_index = find_spell_record(table, 1515)
    table.set_uint32(record_index, 38, 1)
    table.set_uint32(record_index, 39, 1)
    columns = _load_spell_columns()
    row = export_spell_row(table, 1515)
    values_part = row.split("VALUES (", maxsplit=1)[1].rsplit(");", maxsplit=1)[0]
    prefix = values_part.split("'Tame Beast'", maxsplit=1)[0]
    parts = [part.strip() for part in prefix.split(",")]
    assert parts[columns.index("BaseLevel")] == "1"
    assert parts[columns.index("SpellLevel")] == "1"
    assert "4294967295" not in row

