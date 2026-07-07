"""Schema-driven SQL emission from snapshot TableSchema definitions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from aracgen.snapshot_model import COLUMN_ALIASES, ColumnDef, TableSchema

FloatFormatter = Callable[[float], str]


def default_float_format(value: float) -> str:
    return str(value)


def compact_float_format(value: float) -> str:
    return f"{value:g}"


def typed_default(column: ColumnDef) -> Any:
    default = column.default
    if default is None:
        return None
    column_type = column.type.lower()
    if "int" in column_type:
        return int(default)
    if any(token in column_type for token in ("float", "double", "decimal")):
        return float(default)
    return default


def resolve_logical_column(schema: TableSchema, logical: str) -> str:
    if schema.has_column(logical):
        return logical
    if logical in COLUMN_ALIASES.get(schema.table, {}):
        return schema.resolve_logical(logical)
    msg = f"Unknown logical field {logical!r} for table {schema.table!r}"
    raise ValueError(msg)


def column_uses_signed_int(column: ColumnDef) -> bool:
    column_type = column.type.lower()
    return "int" in column_type and "unsigned" not in column_type


def normalize_int_for_column(value: int, column: ColumnDef) -> int:
    if not column_uses_signed_int(column):
        return value
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        return value - 0x100000000
    return value


def prepare_row(schema: TableSchema, logical_values: Mapping[str, Any]) -> dict[str, Any]:
    column_by_name = {column.name: column for column in schema.columns}
    row = {column.name: typed_default(column) for column in schema.columns}
    for logical, value in logical_values.items():
        physical = resolve_logical_column(schema, logical)
        if isinstance(value, int):
            value = normalize_int_for_column(value, column_by_name[physical])
        row[physical] = value
    return row


def format_sql_literal(
    value: Any,
    *,
    float_format: FloatFormatter = default_float_format,
) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return float_format(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "''")
        return f"'{escaped}'"
    return str(value)


def row_values(schema: TableSchema, row: Mapping[str, Any]) -> list[Any]:
    columns = schema.column_names()
    return [row[column] for column in columns]


def render_insert(
    table: str,
    schema: TableSchema,
    logical_values: Mapping[str, Any],
    *,
    float_format: FloatFormatter = default_float_format,
) -> str:
    row = prepare_row(schema, logical_values)
    columns = schema.column_names()
    column_sql = ", ".join(f"`{name}`" for name in columns)
    values_sql = ", ".join(
        format_sql_literal(row[name], float_format=float_format) for name in columns
    )
    return f"INSERT INTO `{table}` ({column_sql}) VALUES ({values_sql});"


def render_replace(
    table: str,
    schema: TableSchema,
    logical_values: Mapping[str, Any],
    *,
    float_format: FloatFormatter = default_float_format,
) -> str:
    return render_insert(
        table,
        schema,
        logical_values,
        float_format=float_format,
    ).replace(
        "INSERT INTO",
        "REPLACE INTO",
        1,
    )


def render_insert_bulk(
    table: str,
    schema: TableSchema,
    rows: Sequence[Mapping[str, Any]],
    *,
    float_format: FloatFormatter = default_float_format,
) -> str:
    if not rows:
        msg = "render_insert_bulk requires at least one row"
        raise ValueError(msg)
    columns = schema.column_names()
    column_sql = ", ".join(f"`{name}`" for name in columns)
    value_groups: list[str] = []
    for logical in rows:
        row = prepare_row(schema, logical)
        rendered = ", ".join(
            format_sql_literal(row[name], float_format=float_format) for name in columns
        )
        value_groups.append(f"({rendered})")
    return (
        f"INSERT INTO `{table}` ({column_sql}) VALUES\n"
        + ",\n".join(value_groups)
        + ";"
    )


def render_update(
    table: str,
    schema: TableSchema,
    set_values: Mapping[str, Any],
    where_values: Mapping[str, Any],
    *,
    float_format: FloatFormatter = default_float_format,
) -> str:
    column_by_name = {column.name: column for column in schema.columns}
    set_parts: list[str] = []
    for logical, value in set_values.items():
        physical = resolve_logical_column(schema, logical)
        if isinstance(value, int):
            value = normalize_int_for_column(value, column_by_name[physical])
        set_parts.append(
            f"`{physical}` = {format_sql_literal(value, float_format=float_format)}"
        )
    where_parts: list[str] = []
    for logical, value in where_values.items():
        physical = resolve_logical_column(schema, logical)
        if isinstance(value, int):
            value = normalize_int_for_column(value, column_by_name[physical])
        where_parts.append(
            f"`{physical}` = {format_sql_literal(value, float_format=float_format)}"
        )
    return (
        f"UPDATE `{table}` SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)};"
    )


def render_insert_lines(
    table: str,
    schema: TableSchema,
    rows: list[Mapping[str, Any]],
    *,
    float_format: FloatFormatter = default_float_format,
) -> list[str]:
    return [
        render_insert(table, schema, row, float_format=float_format) for row in rows
    ]
